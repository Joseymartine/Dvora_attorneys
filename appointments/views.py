from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.db import transaction
from django.utils import timezone
from django.views import View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from core.access import is_administrator, accessible_appointments
from clients.models import Client
from .forms import ScheduleForm, LawyerScheduleForm, ConsultationRequestForm
from .models import Appointment
from .services import save_appointment


def is_lawyer(user):
    return user.groups.filter(name='Lawyers').exists()


def linked_client(user):
    return Client.objects.filter(user=user).first()


class AppointmentAccessMixin(LoginRequiredMixin, PermissionRequiredMixin):
    model = Appointment

    def has_permission(self):
        user = self.request.user
        role_allowed = is_administrator(user) or is_lawyer(user) or (user.groups.filter(name='Clients').exists() and linked_client(user) is not None)
        return role_allowed and super().has_permission()

    def get_queryset(self):
        qs = super().get_queryset().select_related('client', 'assigned_lawyer')
        return accessible_appointments(self.request.user, qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['appointment_administrator'] = is_administrator(user)
        context['appointment_client'] = not is_administrator(user) and not is_lawyer(user)
        appointment = getattr(self, 'object', None)
        context['can_approve_appointment'] = bool(
            appointment and appointment.status == Appointment.Status.REQUESTED
            and appointment.assigned_lawyer_id == user.pk and is_lawyer(user)
            and user.has_perm('appointments.change_appointment')
        )
        context['can_create_appointment'] = user.has_perm('appointments.add_appointment') and (is_administrator(user) or not is_lawyer(user))
        context['can_edit_appointment'] = user.has_perm('appointments.change_appointment') and (is_administrator(user) or is_lawyer(user))
        return context


class SaveAppointmentMixin:
    def form_valid(self, form):
        try:
            self.object = save_appointment(form.instance)
        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        response = HttpResponseRedirect(self.get_success_url())
        messages.success(self.request, 'Appointment saved successfully.')
        return response


class AppointmentListView(AppointmentAccessMixin, ListView):
    permission_required = 'appointments.view_appointment'
    context_object_name = 'appointments'
    paginate_by = 20


class AppointmentDetailView(AppointmentAccessMixin, DetailView):
    permission_required = 'appointments.view_appointment'


class AppointmentCreateView(AppointmentAccessMixin, SaveAppointmentMixin, CreateView):
    permission_required = ('appointments.add_appointment', 'appointments.view_appointment')

    def has_permission(self):
        return super().has_permission() and (is_administrator(self.request.user) or not is_lawyer(self.request.user))

    def get_form_class(self):
        return ScheduleForm if is_administrator(self.request.user) else ConsultationRequestForm

    def form_valid(self, form):
        if not is_administrator(self.request.user):
            form.instance.client = linked_client(self.request.user)
            form.instance.status = Appointment.Status.REQUESTED
            form.instance.assigned_lawyer = None
        return super().form_valid(form)


class AppointmentUpdateView(AppointmentAccessMixin, SaveAppointmentMixin, UpdateView):
    permission_required = ('appointments.change_appointment', 'appointments.view_appointment')

    def has_permission(self):
        return super().has_permission() and (is_administrator(self.request.user) or is_lawyer(self.request.user))

    def get_form_class(self):
        return ScheduleForm if is_administrator(self.request.user) else LawyerScheduleForm



class AppointmentApproveView(AppointmentAccessMixin, SingleObjectMixin, View):
    permission_required = ('appointments.change_appointment', 'appointments.view_appointment')

    def has_permission(self):
        return super().has_permission() and is_lawyer(self.request.user)

    def post(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        with transaction.atomic():
            appointment = get_object_or_404(
                self.get_queryset().select_for_update(of=('self',)),
                pk=kwargs['pk'], assigned_lawyer=request.user,
            )
            if appointment.status != Appointment.Status.REQUESTED:
                messages.error(request, 'Only pending requests can be approved.')
            elif appointment.starts_at <= timezone.now():
                messages.error(request, 'This requested time has passed. Reschedule before approving.')
            else:
                appointment.status = Appointment.Status.CONFIRMED
                try:
                    save_appointment(appointment)
                except ValidationError as error:
                    messages.error(request, ' '.join(error.messages))
                else:
                    messages.success(request, 'Appointment approved. The client can now see the confirmation.')
        return HttpResponseRedirect(appointment.get_absolute_url())
