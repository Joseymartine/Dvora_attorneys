from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Client


class ClientPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser('staff', password='Test-password-123')
        cls.user = get_user_model().objects.create_user('regular')
        cls.record = Client.objects.create(first_name='Asha', last_name='Test', phone='+255700000000')

    def test_access_requires_staff_for_every_page(self):
        urls = [reverse('clients:list'), reverse('clients:create')]
        urls += [reverse(f'clients:{action}', args=[self.record.pk]) for action in ['detail', 'update', 'delete']]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
                self.assertEqual(self.client.post(url, {}).status_code, 302)
        self.client.force_login(self.user)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_create_read_update_and_confirm_delete(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('clients:list')), 'Asha Test')
        self.assertContains(self.client.get(reverse('clients:create')), 'Save client')
        data = {'first_name': 'Neema', 'last_name': 'Example', 'phone': '0712345678', 'email': 'neema@example.com', 'address': 'Dar es Salaam'}
        response = self.client.post(reverse('clients:create'), data)
        record = Client.objects.get(first_name='Neema')
        self.assertRedirects(response, reverse('clients:detail', args=[record.pk]))
        edit_url = reverse('clients:update', args=[record.pk])
        self.assertContains(self.client.get(edit_url), 'neema@example.com')
        data['phone'] = '0799999999'
        self.assertRedirects(self.client.post(edit_url, data), reverse('clients:detail', args=[record.pk]))
        record.refresh_from_db()
        self.assertEqual(record.phone, '0799999999')
        delete_url = reverse('clients:delete', args=[record.pk])
        self.assertContains(self.client.get(delete_url), 'Delete client')
        self.assertTrue(Client.objects.filter(pk=record.pk).exists())
        self.assertRedirects(self.client.post(delete_url), reverse('clients:list'))
        self.assertFalse(Client.objects.filter(pk=record.pk).exists())

    def test_invalid_input_does_not_create_client(self):
        self.client.force_login(self.staff)
        count = Client.objects.count()
        response = self.client.post(reverse('clients:create'), {'email': 'invalid'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(Client.objects.count(), count)

    def test_missing_client_returns_404(self):
        self.client.force_login(self.staff)
        for action in ['detail', 'update', 'delete']:
            self.assertEqual(self.client.get(reverse(f'clients:{action}', args=[99999])).status_code, 404)

    def test_delete_requires_csrf_token(self):
        from django.test import Client as Browser
        browser = Browser(enforce_csrf_checks=True)
        browser.force_login(self.staff)
        self.assertEqual(browser.post(reverse('clients:delete', args=[self.record.pk])).status_code, 403)
        self.assertTrue(Client.objects.filter(pk=self.record.pk).exists())


class ClientConfidentialityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        from django.contrib.auth.models import Group
        from cases.models import Case
        call_command('setup_client_roles', verbosity=0)
        cls.lawyer = get_user_model().objects.create_user('lawyer', is_staff=True)
        cls.other = get_user_model().objects.create_user('other')
        cls.administrator = get_user_model().objects.create_user('administrator')
        cls.lawyer.groups.add(Group.objects.get(name='Lawyers'))
        cls.other.groups.add(Group.objects.get(name='Lawyers'))
        cls.administrator.groups.add(Group.objects.get(name='Administrators'))
        cls.assigned = Client.objects.create(first_name='Assigned', last_name='Client', phone='0700000000')
        cls.hidden = Client.objects.create(first_name='Hidden', last_name='Client', phone='0711111111')
        cls.unassigned = Client.objects.create(first_name='Unassigned', last_name='Client', phone='0722222222')
        cls.case = Case.objects.create(case_number='CONF-1', title='First', client=cls.assigned, assigned_lawyer=cls.lawyer)
        Case.objects.create(case_number='CONF-2', title='Second', client=cls.assigned, assigned_lawyer=cls.lawyer)
        Case.objects.create(case_number='CONF-3', title='Other', client=cls.hidden, assigned_lawyer=cls.other)

    def test_scoped_list_has_no_leaks_or_duplicates(self):
        self.client.force_login(self.lawyer)
        response = self.client.get(reverse('clients:list'))
        self.assertEqual(list(response.context['clients']), [self.assigned])
        self.assertNotContains(response, 'Hidden Client')
        self.assertNotContains(response, 'Unassigned Client')
        self.assertNotContains(response, reverse('clients:create'))
        self.assertEqual(response.context['paginator'].count, 1)
        response = self.client.get(reverse('clients:detail', args=[self.assigned.pk]))
        self.assertNotContains(response, reverse('clients:delete', args=[self.assigned.pk]))

    def test_assigned_lawyer_can_update_client(self):
        self.client.force_login(self.lawyer)
        url = reverse('clients:update', args=[self.assigned.pk])
        data = {'first_name': 'Assigned', 'last_name': 'Client', 'phone': '0799999999'}
        self.assertRedirects(self.client.post(url, data), reverse('clients:detail', args=[self.assigned.pk]))
        self.assigned.refresh_from_db()
        self.assertEqual(self.assigned.phone, '0799999999')

    def test_other_and_unassigned_clients_are_inaccessible(self):
        self.client.force_login(self.lawyer)
        for record in [self.hidden, self.unassigned]:
            for action in ['detail', 'update']:
                url = reverse(f'clients:{action}', args=[record.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                if action == 'update':
                    self.assertEqual(self.client.post(url, {'phone': 'FORGED'}).status_code, 404)
            record.refresh_from_db()
            self.assertNotEqual(record.phone, 'FORGED')

    def test_reassignment_revokes_access(self):
        from cases.models import Case
        Case.objects.filter(client=self.assigned).update(assigned_lawyer=self.other)
        self.client.force_login(self.lawyer)
        self.assertNotContains(self.client.get(reverse('clients:list')), 'Assigned Client')
        self.assertEqual(self.client.get(reverse('clients:detail', args=[self.assigned.pk])).status_code, 404)

    def test_extra_permissions_do_not_allow_lawyer_create_or_delete(self):
        from django.contrib.auth.models import Permission
        self.lawyer.user_permissions.add(*Permission.objects.filter(content_type__app_label='clients'))
        self.client.force_login(self.lawyer)
        for url in [reverse('clients:create'), reverse('clients:delete', args=[self.assigned.pk])]:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.assertTrue(Client.objects.filter(pk=self.assigned.pk).exists())

    def test_administrator_sees_all_and_linked_delete_is_handled(self):
        self.client.force_login(self.administrator)
        response = self.client.get(reverse('clients:list'))
        self.assertEqual(response.context['paginator'].count, 3)
        response = self.client.post(reverse('clients:delete', args=[self.assigned.pk]))
        self.assertContains(response, 'This client has linked cases')
        self.assertTrue(Client.objects.filter(pk=self.assigned.pk).exists())

    def test_model_permission_still_required(self):
        from django.contrib.auth.models import Group
        Group.objects.get(name='Lawyers').permissions.clear()
        self.client.force_login(self.lawyer)
        self.assertEqual(self.client.get(reverse('clients:list')).status_code, 403)

    def test_staff_lawyer_cannot_bypass_scope_in_admin(self):
        self.client.force_login(self.lawyer)
        self.assertEqual(self.client.get(reverse('admin:clients_client_changelist')).status_code, 403)
        for record in [self.assigned, self.hidden]:
            url = reverse('admin:clients_client_change', args=[record.pk])
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {'first_name': 'FORGED'}).status_code, 403)
