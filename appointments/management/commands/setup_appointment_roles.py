from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Add appointment permissions to Administrators, Lawyers, and Clients.'

    def handle(self, *args, **options):
        roles = [('Administrators', ['view', 'add', 'change']), ('Lawyers', ['view', 'change']), ('Clients', ['view', 'add'])]
        for name, actions in roles:
            group, _ = Group.objects.get_or_create(name=name)
            for action in actions:
                group.permissions.add(Permission.objects.get(content_type__app_label='appointments', content_type__model='appointment', codename=f'{action}_appointment'))
            group.permissions.remove(Permission.objects.get(content_type__app_label='appointments', content_type__model='appointment', codename='delete_appointment'))
            self.stdout.write(self.style.SUCCESS(f'{name}: appointment permissions configured.'))
