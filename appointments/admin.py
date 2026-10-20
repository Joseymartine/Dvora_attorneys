from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'client', 'assigned_lawyer', 'starts_at', 'ends_at', 'status']
    list_filter = ['status', 'starts_at']
    search_fields = ['title', 'client__first_name', 'client__last_name']
    list_select_related = ['client', 'assigned_lawyer']
    readonly_fields = [field.name for field in Appointment._meta.fields]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.none()
