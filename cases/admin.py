from django.contrib import admin
from .models import Case


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['case_number', 'title', 'client', 'assigned_lawyer', 'status', 'date_opened']
    list_filter = ['status', 'date_opened']
    search_fields = ['case_number', 'title', 'client__first_name', 'client__last_name']
    list_select_related = ['client', 'assigned_lawyer']
    readonly_fields = ['created_at', 'updated_at']

    # Keep this separate interface restricted to superusers. Lawyers use the
    # case pages, where assignments and record access are explicitly enforced.
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
