from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'phone', 'user', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']

    # Lawyers use the scoped client pages, never the unscoped admin interface.
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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if request.user.is_superuser else queryset.none()
