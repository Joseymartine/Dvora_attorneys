from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from core.access import is_administrator, accessible_clients
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import ClientForm
from .models import Client


class ClientAccessMixin(LoginRequiredMixin, PermissionRequiredMixin):
    model = Client
    login_url = reverse_lazy('login')

    def has_permission(self):
        user = self.request.user
        return (is_administrator(user) or user.groups.filter(name='Lawyers').exists()) and super().has_permission()

    def get_queryset(self):
        queryset = super().get_queryset()
        return accessible_clients(self.request.user, queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client_administrator'] = is_administrator(self.request.user)
        return context


class AdministratorClientMixin(ClientAccessMixin):
    def has_permission(self):
        return is_administrator(self.request.user) and super().has_permission()


class ClientListView(ClientAccessMixin, ListView):
    permission_required = 'clients.view_client'
    model = Client
    context_object_name = 'clients'
    paginate_by = 20


class ClientDetailView(ClientAccessMixin, DetailView):
    permission_required = 'clients.view_client'
    model = Client


class ClientCreateView(AdministratorClientMixin, CreateView):
    permission_required = ('clients.add_client', 'clients.view_client')
    model = Client
    form_class = ClientForm

    def get_success_url(self):
        return reverse_lazy('clients:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, 'Client added successfully.')
        return super().form_valid(form)


class ClientUpdateView(ClientAccessMixin, UpdateView):
    permission_required = ('clients.change_client', 'clients.view_client')
    model = Client
    form_class = ClientForm

    def get_success_url(self):
        return reverse_lazy('clients:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, 'Client updated successfully.')
        return super().form_valid(form)


class ClientDeleteView(AdministratorClientMixin, DeleteView):
    permission_required = ('clients.delete_client', 'clients.view_client')
    model = Client
    success_url = reverse_lazy('clients:list')

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            form.add_error(None, 'This client has linked cases or appointments and cannot be deleted. Reassign or remove those records first.')
            return self.form_invalid(form)
        messages.success(self.request, 'Client deleted successfully.')
        return response
