from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from clients.models import Client
from cases.models import Case
from appointments.models import Appointment


class APITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for command in ['setup_case_roles', 'setup_client_roles', 'setup_appointment_roles']:
            call_command(command, verbosity=0)
        User = get_user_model()
        cls.administrator = User.objects.create_user('administrator', password='Test-password-123')
        cls.administrator.groups.add(Group.objects.get(name='Administrators'))
        cls.lawyer = User.objects.create_user('lawyer')
        cls.other = User.objects.create_user('other')
        for lawyer in [cls.lawyer, cls.other]:
            lawyer.groups.add(Group.objects.get(name='Lawyers'))
        cls.customer = User.objects.create_user('customer')
        cls.customer.groups.add(Group.objects.get(name='Clients'))
        cls.other_customer = User.objects.create_user('other-customer')
        cls.other_customer.groups.add(Group.objects.get(name='Clients'))
        cls.staff = User.objects.create_user('plain-staff', is_staff=True)
        cls.unlinked = User.objects.create_user('unlinked')
        cls.unlinked.groups.add(Group.objects.get(name='Clients'))
        cls.record = Client.objects.create(first_name='Visible', last_name='Client', phone='0700000000', user=cls.customer)
        cls.hidden = Client.objects.create(first_name='Private', last_name='Client', phone='0711111111', user=cls.other_customer)
        cls.case = Case.objects.create(case_number='API-001', title='Visible case', client=cls.record, assigned_lawyer=cls.lawyer)
        cls.hidden_case = Case.objects.create(case_number='API-002', title='Private case', client=cls.hidden, assigned_lawyer=cls.other)
        cls.start = (timezone.now() + timedelta(days=7)).replace(second=0, microsecond=0)
        cls.appointment = Appointment.objects.create(title='Visible booking', client=cls.record, assigned_lawyer=cls.lawyer, starts_at=cls.start, ends_at=cls.start + timedelta(hours=1), status='confirmed')
        cls.hidden_appointment = Appointment.objects.create(title='Private booking', client=cls.hidden, assigned_lawyer=cls.other, starts_at=cls.start, ends_at=cls.start + timedelta(hours=1), status='confirmed')

    def setUp(self):
        self.api = APIClient()

    def appointment_data(self, start=None):
        start = start or self.start + timedelta(days=1)
        return {'title': 'New booking', 'client': self.record.pk, 'assigned_lawyer': self.lawyer.pk, 'starts_at': start.isoformat(), 'ends_at': (start + timedelta(hours=1)).isoformat(), 'status': 'confirmed', 'notes': 'Shared'}

    def test_anonymous_staff_and_unlinked_cannot_access_records(self):
        for user in [None, self.staff, self.unlinked]:
            self.api.force_authenticate(user=user)
            for resource in ['clients', 'cases', 'appointments']:
                self.assertEqual(self.api.get(f'/api/{resource}/').status_code, 403)
                self.assertEqual(self.api.post(f'/api/{resource}/', {}, format='json').status_code, 403)

    def test_administrator_client_crud_and_protected_delete(self):
        self.api.force_authenticate(self.administrator)
        response = self.api.post('/api/clients/', {'first_name': 'New', 'last_name': 'Person', 'phone': '0799999999'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/clients/{response.data['id']}/"
        self.assertNotIn('user', response.data)
        self.assertEqual(self.api.patch(url, {'phone': '0788888888'}, format='json').status_code, 200)
        self.assertEqual(self.api.delete(url).status_code, 204)
        self.assertEqual(self.api.delete(f'/api/clients/{self.record.pk}/').status_code, 400)
        self.assertTrue(Client.objects.filter(pk=self.record.pk).exists())

    def test_client_field_validation_and_login_link_protected(self):
        self.api.force_authenticate(self.administrator)
        self.assertEqual(self.api.post('/api/clients/', {'email': 'invalid'}, format='json').status_code, 400)
        self.assertEqual(self.api.patch(f'/api/clients/{self.record.pk}/', {'user': self.other_customer.pk}, format='json').status_code, 400)
        self.record.refresh_from_db()
        self.assertEqual(self.record.user, self.customer)

    def test_lawyer_lists_and_direct_urls_are_scoped(self):
        self.api.force_authenticate(self.lawyer)
        for resource, visible, hidden in [('clients', self.record, self.hidden), ('cases', self.case, self.hidden_case), ('appointments', self.appointment, self.hidden_appointment)]:
            with self.subTest(resource=resource):
                response = self.api.get(f'/api/{resource}/')
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['count'], 1)
                self.assertEqual(response.data['results'][0]['id'], visible.pk)
                self.assertEqual(self.api.get(f'/api/{resource}/{hidden.pk}/').status_code, 404)
                self.assertEqual(self.api.patch(f'/api/{resource}/{hidden.pk}/', {'title': 'Forged'}, format='json').status_code, 404)
                self.assertEqual(self.api.post(f'/api/{resource}/', {}, format='json').status_code, 403)

    def test_lawyer_can_edit_visible_records_not_reassign(self):
        self.api.force_authenticate(self.lawyer)
        self.assertEqual(self.api.patch(f'/api/clients/{self.record.pk}/', {'phone': '0788888888'}, format='json').status_code, 200)
        self.assertEqual(self.api.patch(f'/api/cases/{self.case.pk}/', {'status': 'closed'}, format='json').status_code, 200)
        for resource, record in [('cases', self.case), ('appointments', self.appointment)]:
            for field, value in [('client', self.hidden.pk), ('assigned_lawyer', self.other.pk)]:
                response = self.api.patch(f'/api/{resource}/{record.pk}/', {field: value}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
            record.refresh_from_db()
            self.assertEqual(record.assigned_lawyer, self.lawyer)
        self.assertEqual(self.api.patch(f'/api/cases/{self.case.pk}/', {'case_number': 'Forged'}, format='json').status_code, 400)
        self.assertEqual(self.api.delete(f'/api/clients/{self.record.pk}/').status_code, 403)
        self.assertEqual(self.api.delete(f'/api/cases/{self.case.pk}/').status_code, 403)

    def test_case_admin_crud_unique_number_and_invalid_lawyer(self):
        self.api.force_authenticate(self.administrator)
        data = {'case_number': 'API-003', 'title': 'New case', 'client': self.record.pk, 'assigned_lawyer': self.lawyer.pk}
        response = self.api.post('/api/cases/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/cases/{response.data['id']}/"
        self.assertEqual(self.api.post('/api/cases/', data, format='json').status_code, 400)
        self.assertEqual(self.api.put(url, dict(data, assigned_lawyer=self.other.pk), format='json').status_code, 200)
        self.assertEqual(self.api.patch(url, {'assigned_lawyer': self.staff.pk}, format='json').status_code, 400)
        self.assertEqual(self.api.delete(url).status_code, 204)

    def test_appointment_create_overlap_adjacent_and_partial_validation(self):
        self.api.force_authenticate(self.administrator)
        response = self.api.post('/api/appointments/', self.appointment_data(self.start + timedelta(minutes=30)), format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('non_field_errors', response.data)
        response = self.api.post('/api/appointments/', self.appointment_data(self.start + timedelta(hours=1)), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/appointments/{response.data['id']}/"
        self.assertEqual(self.api.patch(url, {'ends_at': self.start.isoformat()}, format='json').status_code, 400)
        self.assertEqual(self.api.patch(url, {'starts_at': (self.start + timedelta(minutes=30)).isoformat()}, format='json').status_code, 400)
        self.assertEqual(self.api.patch(url, {'starts_at': '2020-01-01T10:00:00+03:00'}, format='json').status_code, 400)

    def test_appointment_invalid_status_dates_and_lawyer(self):
        self.api.force_authenticate(self.administrator)
        for changes in [{'status': 'invented'}, {'assigned_lawyer': None}, {'assigned_lawyer': self.staff.pk}, {'ends_at': 'not-a-date'}]:
            data = self.appointment_data()
            data.update(changes)
            self.assertEqual(self.api.post('/api/appointments/', data, format='json').status_code, 400)

    def test_client_request_identity_and_scope(self):
        self.api.force_authenticate(self.customer)
        data = self.appointment_data()
        for name in ['client', 'assigned_lawyer', 'status']:
            del data[name]
        response = self.api.post('/api/appointments/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['client'], self.record.pk)
        self.assertEqual(response.data['status'], 'requested')
        self.assertIsNone(response.data['assigned_lawyer'])
        for name, value in [('client', self.hidden.pk), ('assigned_lawyer', self.other.pk), ('status', 'confirmed')]:
            self.assertEqual(self.api.post('/api/appointments/', dict(data, **{name: value}), format='json').status_code, 400)
        response = self.api.get('/api/appointments/')
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(self.api.get(f'/api/appointments/{self.hidden_appointment.pk}/').status_code, 404)
        self.assertEqual(self.api.patch(f'/api/appointments/{self.appointment.pk}/', {'status': 'cancelled'}, format='json').status_code, 403)
        self.assertEqual(self.api.get('/api/clients/').status_code, 403)
        self.assertEqual(self.api.get('/api/cases/').status_code, 403)

    def test_cancel_preserves_row_frees_slot_and_delete_not_supported(self):
        self.api.force_authenticate(self.lawyer)
        url = f'/api/appointments/{self.appointment.pk}/'
        self.assertEqual(self.api.patch(url, {'status': 'cancelled'}, format='json').status_code, 200)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'cancelled')
        self.api.force_authenticate(self.administrator)
        self.assertEqual(self.api.delete(url).status_code, 405)
        self.assertTrue(Appointment.objects.filter(pk=self.appointment.pk).exists())
        self.assertEqual(self.api.post('/api/appointments/', self.appointment_data(self.start), format='json').status_code, 201)

    def test_reassignment_revokes_access_and_permissions_are_required(self):
        self.api.force_authenticate(self.lawyer)
        self.case.assigned_lawyer = self.other
        self.case.save()
        self.assertEqual(self.api.get(f'/api/cases/{self.case.pk}/').status_code, 404)
        self.assertEqual(self.api.get(f'/api/clients/{self.record.pk}/').status_code, 404)
        Group.objects.get(name='Lawyers').permissions.clear()
        self.api.force_authenticate(get_user_model().objects.get(pk=self.lawyer.pk))
        self.assertEqual(self.api.get('/api/appointments/').status_code, 403)

    def test_extra_model_permissions_do_not_override_role(self):
        self.lawyer.user_permissions.add(*Permission.objects.all())
        self.api.force_authenticate(self.lawyer)
        for resource, record in [('clients', self.record), ('cases', self.case)]:
            self.assertEqual(self.api.post(f'/api/{resource}/', {}, format='json').status_code, 403)
            self.assertEqual(self.api.delete(f'/api/{resource}/{record.pk}/').status_code, 403)
        self.customer.user_permissions.add(*Permission.objects.all())
        self.api.force_authenticate(self.customer)
        self.assertEqual(self.api.patch(f'/api/appointments/{self.appointment.pk}/', {'title': 'Forged'}, format='json').status_code, 403)

    def test_session_auth_csrf_and_browsable_api(self):
        browser = APIClient(enforce_csrf_checks=True)
        browser.force_login(self.administrator)
        response = browser.get('/api/clients/', HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visible')
        self.assertEqual(browser.post('/api/clients/', {'first_name': 'New', 'last_name': 'Person', 'phone': '0700000000'}, format='json').status_code, 403)
        token = browser.cookies['csrftoken'].value
        self.assertEqual(browser.post('/api/clients/', {'first_name': 'New', 'last_name': 'Person', 'phone': '0700000000'}, format='json', HTTP_X_CSRFTOKEN=token).status_code, 201)

    def test_revalidation_at_save_returns_400(self):
        self.api.force_authenticate(self.administrator)
        with patch.object(Appointment, 'full_clean', side_effect=[None, ValidationError('Concurrent booking conflict')]):
            response = self.api.post('/api/appointments/', self.appointment_data(), format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Appointment.objects.count(), 2)
