from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Add client permissions to Administrators and Lawyers without removing existing permissions.'

    def handle(self, *args, **options):
        for name, actions in [('Administrators', ['view', 'add', 'change', 'delete']), ('Lawyers', ['view', 'change'])]:
            group, _ = Group.objects.get_or_create(name=name)
            for action in actions:
                group.permissions.add(Permission.objects.get(
                    content_type__app_label='clients', content_type__model='client', codename=f'{action}_client'))
            self.stdout.write(self.style.SUCCESS(f'{name}: client permissions configured.'))
