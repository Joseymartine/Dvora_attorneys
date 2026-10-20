from rest_framework.permissions import BasePermission
from core.access import is_administrator, is_lawyer
from clients.models import Client


class RecordPermissions(BasePermission):
    """Require both model permissions and the application's role policy."""
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.is_active:
            return False
        model = view.queryset.model
        action = getattr(view, 'action', None)
        operation = {'list': 'view', 'retrieve': 'view', 'create': 'add',
                     'update': 'change', 'partial_update': 'change', 'destroy': 'delete'}.get(action)
        if request.method == 'OPTIONS' or request.method.lower() not in view.action_map:
            operation = 'view'
        if operation is None:
            return False
        label = model._meta.app_label
        name = model._meta.model_name
        if not user.has_perms([f'{label}.view_{name}', f'{label}.{operation}_{name}']):
            return False
        if is_administrator(user):
            return True
        if is_lawyer(user):
            return operation in ['view', 'change']
        return (name == 'appointment' and operation in ['view', 'add']
                and user.groups.filter(name='Clients').exists()
                and Client.objects.filter(user=user).exists())
