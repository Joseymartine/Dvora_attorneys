from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db.models.deletion import ProtectedError
from django.test import TestCase, Client as Browser
from django.urls import reverse
from clients.models import Client
from .models import Case


class CaseWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_case_roles', verbosity=0)
        User = get_user_model()
        cls.admin = User.objects.create_user('administrator')
        cls.admin.groups.add(Group.objects.get(name='Administrators'))
        cls.lawyer = User.objects.create_user('lawyer', password='Test-password-123')
        cls.other = User.objects.create_user('other')
        cls.lawyer.groups.add(Group.objects.get(name='Lawyers'))
        cls.other.groups.add(Group.objects.get(name='Lawyers'))
        cls.regular = User.objects.create_user('regular', is_staff=True)
        cls.client_record = Client.objects.create(first_name='Asha', last_name='Test', phone='0700000000')
        cls.case = Case.objects.create(case_number='DV-001', title='Assigned matter', client=cls.client_record, assigned_lawyer=cls.lawyer)
        cls.hidden = Case.objects.create(case_number='DV-002', title='Private other matter', client=cls.client_record, assigned_lawyer=cls.other)

    def data(self, number='DV-003'):
        return {'case_number': number, 'title': 'New matter', 'client': self.client_record.pk, 'assigned_lawyer': self.lawyer.pk, 'status': 'open', 'date_opened': '2026-10-19', 'description': 'Details'}

    def test_administrator_crud_and_validation(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('cases:list')), self.hidden.title)
        response = self.client.post(reverse('cases:create'), self.data())
        case = Case.objects.get(case_number='DV-003')
        self.assertRedirects(response, case.get_absolute_url())
        data = self.data()
        data['title'] = 'Updated matter'
        self.assertRedirects(self.client.post(reverse('cases:update', args=[case.pk]), data), case.get_absolute_url())
        case.refresh_from_db()
        self.assertEqual(case.title, 'Updated matter')
        response = self.client.post(reverse('cases:create'), self.data())
        self.assertTrue(response.context['form'].errors)
        delete = reverse('cases:delete', args=[case.pk])
        self.assertEqual(self.client.get(delete).status_code, 200)
        self.assertTrue(Case.objects.filter(pk=case.pk).exists())
        self.assertRedirects(self.client.post(delete), reverse('cases:list'))
        self.assertFalse(Case.objects.filter(pk=case.pk).exists())

    def test_lawyer_only_sees_assigned_cases(self):
        self.client.force_login(self.lawyer)
        response = self.client.get(reverse('cases:list'))
        self.assertContains(response, self.case.title)
        self.assertNotContains(response, self.hidden.title)
        for action in ['detail', 'update']:
            url = reverse(f'cases:{action}', args=[self.hidden.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, self.data()).status_code, 404 if action == 'update' else 405)

    def test_lawyer_cannot_change_assignments_even_with_forged_post(self):
        self.client.force_login(self.lawyer)
        data = self.data('FORGED')
        data.update(assigned_lawyer=self.other.pk, status='closed')
        self.assertRedirects(self.client.post(reverse('cases:update', args=[self.case.pk]), data), self.case.get_absolute_url())
        self.case.refresh_from_db()
        self.assertEqual(self.case.assigned_lawyer, self.lawyer)
        self.assertEqual(self.case.case_number, 'DV-001')
        self.assertEqual(self.case.status, 'closed')
        for url in [reverse('cases:create'), reverse('cases:delete', args=[self.case.pk])]:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, data).status_code, 403)

    def test_visitors_and_unprivileged_staff_denied(self):
        urls = [reverse('cases:list'), reverse('cases:create')]
        urls += [reverse(f'cases:{action}', args=[self.case.pk]) for action in ['detail', 'update', 'delete']]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.regular)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, self.data()).status_code, 403)

    def test_invalid_lawyer_rejected(self):
        self.client.force_login(self.admin)
        for user in [self.regular, self.admin]:
            data = self.data()
            data['assigned_lawyer'] = user.pk
            self.assertTrue(self.client.post(reverse('cases:create'), data).context['form'].errors)

    def test_client_and_lawyer_deletion_protected(self):
        for obj in [self.client_record, self.lawyer]:
            with self.assertRaises(ProtectedError):
                obj.delete()

    def test_login_logout_and_csrf(self):
        self.assertRedirects(self.client.post(reverse('login'), {'username': 'lawyer', 'password': 'Test-password-123'}), reverse('cases:list'))
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertRedirects(self.client.post(reverse('logout')), reverse('home'))
        browser = Browser(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        self.assertEqual(browser.post(reverse('cases:delete', args=[self.case.pk])).status_code, 403)

    def test_lawyer_cannot_use_admin_to_bypass_assignment_scope(self):
        self.lawyer.is_staff = True
        self.lawyer.save()
        self.client.force_login(self.lawyer)
        self.assertEqual(self.client.get(reverse('admin:cases_case_change', args=[self.hidden.pk])).status_code, 403)
