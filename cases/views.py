from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from core.access import is_administrator, accessible_cases
from .forms import CaseForm, LawyerCaseForm
from .models import Case



class CaseAccessMixin(LoginRequiredMixin, PermissionRequiredMixin):
    model = Case
    login_url = reverse_lazy('login')

    def has_permission(self):
        user = self.request.user
        return (is_administrator(user) or user.groups.filter(name='Lawyers').exists()) and super().has_permission()

    def get_queryset(self):
        queryset = super().get_queryset().select_related('client', 'assigned_lawyer')
        return accessible_cases(self.request.user, queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['case_administrator'] = is_administrator(self.request.user)
        return context


class AdministratorCaseMixin(CaseAccessMixin):
    def has_permission(self):
        return is_administrator(self.request.user) and super().has_permission()


class CaseListView(CaseAccessMixin, ListView):
    permission_required = 'cases.view_case'
    context_object_name = 'cases'
    paginate_by = 20


class CaseDetailView(CaseAccessMixin, DetailView):
    permission_required = 'cases.view_case'


class CaseCreateView(AdministratorCaseMixin, CreateView):
    permission_required = ('cases.add_case', 'cases.view_case')
    form_class = CaseForm

    def form_valid(self, form):
        messages.success(self.request, 'Case created successfully.')
        return super().form_valid(form)


class CaseUpdateView(CaseAccessMixin, UpdateView):
    permission_required = ('cases.change_case', 'cases.view_case')

    def get_form_class(self):
        return CaseForm if is_administrator(self.request.user) else LawyerCaseForm

    def form_valid(self, form):
        messages.success(self.request, 'Case updated successfully.')
        return super().form_valid(form)


class CaseDeleteView(AdministratorCaseMixin, DeleteView):
    permission_required = ('cases.delete_case', 'cases.view_case')
    success_url = reverse_lazy('cases:list')

    def form_valid(self, form):
        messages.success(self.request, 'Case deleted successfully.')
        return super().form_valid(form)
