from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create case management groups and add their permissions without removing existing permissions.'

    def handle(self, *args, **options):
        for name, actions in [('Administrators', ['view', 'add', 'change', 'delete']), ('Lawyers', ['view', 'change'])]:
            group, _ = Group.objects.get_or_create(name=name)
            for action in actions:
                permission = Permission.objects.get(content_type__app_label='cases', content_type__model='case', codename=f'{action}_case')
                group.permissions.add(permission)
            self.stdout.write(self.style.SUCCESS(f'{name}: case permissions configured.'))
