from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase, Client as Browser
from django.urls import reverse
from django.utils import timezone
from clients.models import Client
from .models import Appointment


class AppointmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_appointment_roles', verbosity=0)
        User = get_user_model()
        cls.administrator = User.objects.create_user('administrator')
        cls.administrator.groups.add(Group.objects.get(name='Administrators'))
        cls.lawyer = User.objects.create_user('lawyer', is_staff=True)
        cls.other = User.objects.create_user('other')
        cls.lawyer.groups.add(Group.objects.get(name='Lawyers'))
        cls.other.groups.add(Group.objects.get(name='Lawyers'))
        cls.customer = User.objects.create_user('customer', password='Test-password-123')
        cls.customer.groups.add(Group.objects.get(name='Clients'))
        cls.other_customer = User.objects.create_user('other-customer')
        cls.other_customer.groups.add(Group.objects.get(name='Clients'))
        cls.record = Client.objects.create(first_name='First', last_name='Client', phone='0700000000', user=cls.customer)
        cls.hidden = Client.objects.create(first_name='Other', last_name='Client', phone='0711111111', user=cls.other_customer)
        cls.start = (timezone.now() + timedelta(days=5)).replace(second=0, microsecond=0)
        cls.appointment = Appointment.objects.create(title='Visible consultation', client=cls.record, assigned_lawyer=cls.lawyer, starts_at=cls.start, ends_at=cls.start + timedelta(hours=1), status='confirmed')
        cls.private = Appointment.objects.create(title='Private consultation', client=cls.hidden, assigned_lawyer=cls.other, starts_at=cls.start, ends_at=cls.start + timedelta(hours=1), status='confirmed')

    def data(self, start=None):
        start = start or self.start + timedelta(days=1)
        return {'title': 'New consultation', 'client': self.record.pk, 'assigned_lawyer': self.lawyer.pk, 'starts_at': timezone.localtime(start).strftime('%Y-%m-%dT%H:%M'), 'ends_at': timezone.localtime(start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'), 'status': 'confirmed', 'notes': 'Shared notes'}

    def test_administrator_crud(self):
        self.client.force_login(self.administrator)
        self.assertContains(self.client.get(reverse('appointments:list')), self.private.title)
        response = self.client.post(reverse('appointments:create'), self.data())
        appointment = Appointment.objects.get(title='New consultation')
        self.assertRedirects(response, appointment.get_absolute_url())
        data = self.data()
        data['title'] = 'Edited consultation'
        self.assertRedirects(self.client.post(reverse('appointments:update', args=[appointment.pk]), data), appointment.get_absolute_url())
        data['status'] = 'cancelled'
        self.assertRedirects(self.client.post(reverse('appointments:update', args=[appointment.pk]), data), appointment.get_absolute_url())
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'cancelled')
        self.assertTrue(Appointment.objects.filter(pk=appointment.pk).exists())

    def test_lawyer_scope_and_forged_assignment(self):
        self.client.force_login(self.lawyer)
        self.assertNotContains(self.client.get(reverse('appointments:list')), self.private.title)
        for action in ['detail', 'update']:
            url = reverse(f'appointments:{action}', args=[self.private.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
        data = self.data()
        data.update(client=self.hidden.pk, assigned_lawyer=self.other.pk)
        self.assertRedirects(self.client.post(reverse('appointments:update', args=[self.appointment.pk]), data), self.appointment.get_absolute_url())
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.client, self.record)
        self.assertEqual(self.appointment.assigned_lawyer, self.lawyer)
        for url in [reverse('appointments:create')]:
            self.assertEqual(self.client.post(url, data).status_code, 403)

    def test_client_request_ignores_forged_identity_lawyer_and_status(self):
        self.client.force_login(self.customer)
        data = self.data()
        data['client'] = self.hidden.pk
        response = self.client.post(reverse('appointments:create'), data)
        appointment = Appointment.objects.get(title='New consultation')
        self.assertRedirects(response, appointment.get_absolute_url())
        self.assertEqual(appointment.client, self.record)
        self.assertIsNone(appointment.assigned_lawyer)
        self.assertEqual(appointment.status, 'requested')
        self.assertNotContains(self.client.get(appointment.get_absolute_url()), 'Edit appointment')

    def test_client_cannot_read_other_requests_or_update_delete(self):
        self.customer.user_permissions.add(*Permission.objects.filter(content_type__app_label='appointments'))
        self.client.force_login(self.customer)
        self.assertNotContains(self.client.get(reverse('appointments:list')), self.private.title)
        self.assertEqual(self.client.get(self.private.get_absolute_url()).status_code, 404)
        for action in ['update']:
            url = reverse(f'appointments:{action}', args=[self.appointment.pk])
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, self.data()).status_code, 403)

    def test_no_access_for_visitors_unlinked_or_plain_staff(self):
        self.assertEqual(self.client.get(reverse('appointments:list')).status_code, 302)
        User = get_user_model()
        unlinked = User.objects.create_user('unlinked')
        unlinked.groups.add(Group.objects.get(name='Clients'))
        staff = User.objects.create_user('staff', is_staff=True)
        for user in [unlinked, staff]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('appointments:list')).status_code, 403)
            self.assertEqual(self.client.post(reverse('appointments:create'), self.data()).status_code, 403)

    def test_overlap_rejected_and_adjacent_time_allowed(self):
        self.client.force_login(self.administrator)
        response = self.client.post(reverse('appointments:create'), self.data(self.start + timedelta(minutes=30)))
        self.assertContains(response, 'already has an appointment')
        self.assertEqual(Appointment.objects.count(), 2)
        response = self.client.post(reverse('appointments:create'), self.data(self.start + timedelta(hours=1)))
        self.assertEqual(response.status_code, 302)

    def test_cancelled_booking_frees_time(self):
        self.appointment.status = 'cancelled'
        self.appointment.save()
        self.client.force_login(self.administrator)
        self.assertEqual(self.client.post(reverse('appointments:create'), self.data(self.start)).status_code, 302)

    def test_invalid_dates_lawyer_and_missing_assignment(self):
        self.client.force_login(self.administrator)
        for changes in [
            {'ends_at': self.data()['starts_at']},
            {'starts_at': '2020-01-01T10:00', 'ends_at': '2020-01-01T11:00'},
            {'assigned_lawyer': ''},
            {'assigned_lawyer': self.customer.pk},
            {'status': 'invented'},
        ]:
            data = self.data()
            data.update(changes)
            with self.subTest(changes=changes):
                response = self.client.post(reverse('appointments:create'), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_existing_booking_does_not_conflict_with_itself(self):
        self.client.force_login(self.lawyer)
        self.assertEqual(self.client.post(reverse('appointments:update', args=[self.appointment.pk]), self.data(self.start)).status_code, 302)

    def test_client_login_redirect_and_csrf(self):
        self.assertRedirects(self.client.post(reverse('login'), {'username': 'customer', 'password': 'Test-password-123'}), reverse('appointments:list'))
        browser = Browser(enforce_csrf_checks=True)
        browser.force_login(self.administrator)
        self.assertEqual(browser.post(reverse('appointments:update', args=[self.appointment.pk]), self.data()).status_code, 403)

    def test_admin_cannot_be_used_to_bypass_schedule_validation(self):
        self.client.force_login(self.lawyer)
        self.assertEqual(self.client.get(reverse('admin:appointments_appointment_changelist')).status_code, 403)

    def test_client_and_lawyer_deletion_are_protected(self):
        from django.db.models.deletion import ProtectedError
        for obj in [self.record, self.lawyer]:
            with self.assertRaises(ProtectedError):
                obj.delete()

    def test_permanent_delete_unavailable_for_every_role(self):
        superuser = get_user_model().objects.create_superuser('superuser', password='Test-password-123')
        for user in [superuser, self.administrator, self.lawyer, self.customer]:
            self.client.force_login(user)
            url = f'/appointments/{self.appointment.pk}/delete/'
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Appointment.objects.filter(pk=self.appointment.pk).exists())
        self.client.force_login(superuser)
        self.assertEqual(self.client.post(reverse('admin:appointments_appointment_delete', args=[self.appointment.pk])).status_code, 403)

    def test_assigned_lawyer_can_cancel_and_keep_history(self):
        self.client.force_login(self.lawyer)
        data = self.data(self.start)
        data['status'] = 'cancelled'
        self.assertRedirects(self.client.post(reverse('appointments:update', args=[self.appointment.pk]), data), self.appointment.get_absolute_url())
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'cancelled')
        self.assertEqual(Appointment.objects.count(), 2)

    def test_appointment_pages_render_details_and_local_times(self):
        self.client.force_login(self.administrator)
        response = self.client.get(reverse('appointments:list'))
        self.assertTemplateUsed(response, 'appointments/appointment_list.html')
        self.assertContains(response, self.appointment.title)
        self.assertContains(response, timezone.localtime(self.start).strftime('%d %b %Y, %H:%M'))
        response = self.client.get(self.appointment.get_absolute_url())
        self.assertTemplateUsed(response, 'appointments/appointment_detail.html')
        self.assertContains(response, str(self.record))
        self.assertContains(response, 'Confirmed')
        self.assertNotContains(response, 'Delete appointment')
        response = self.client.get(reverse('appointments:update', args=[self.appointment.pk]))
        self.assertTemplateUsed(response, 'appointments/appointment_form.html')
        self.assertContains(response, timezone.localtime(self.start).strftime('%Y-%m-%dT%H:%M'))
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, 'datetime-local')


    def pending_request(self):
        return Appointment.objects.create(
            title='Pending approval', client=self.record, assigned_lawyer=self.lawyer,
            starts_at=self.start + timedelta(days=2),
            ends_at=self.start + timedelta(days=2, hours=1),
        )

    def test_assigned_lawyer_approves_and_client_sees_confirmation(self):
        appointment = self.pending_request()
        self.client.force_login(self.lawyer)
        self.assertContains(self.client.get(appointment.get_absolute_url()), 'Approve appointment')
        url = reverse('appointments:approve', args=[appointment.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), appointment.get_absolute_url())
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
        self.client.force_login(self.customer)
        response = self.client.get(appointment.get_absolute_url())
        self.assertContains(response, 'Confirmed')
        self.assertNotContains(response, 'Approve appointment')

    def test_approval_requires_assignment_and_lawyer_role(self):
        appointment = self.pending_request()
        url = reverse('appointments:approve', args=[appointment.pk])
        for user, status in [(self.customer, 403), (self.administrator, 403), (self.other, 404)]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(url).status_code, status)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.REQUESTED)

    def test_approval_preserves_cancelled_status(self):
        appointment = self.pending_request()
        appointment.status = Appointment.Status.CANCELLED
        appointment.save()
        self.client.force_login(self.lawyer)
        self.client.post(reverse('appointments:approve', args=[appointment.pk]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)

    def test_approval_rejects_past_request_and_requires_csrf(self):
        appointment = self.pending_request()
        url = reverse('appointments:approve', args=[appointment.pk])
        browser = Browser(enforce_csrf_checks=True)
        browser.force_login(self.lawyer)
        self.assertEqual(browser.post(url).status_code, 403)
        appointment.starts_at = timezone.now() - timedelta(hours=2)
        appointment.ends_at = timezone.now() - timedelta(hours=1)
        appointment.save()
        self.client.force_login(self.lawyer)
        self.client.post(url)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.REQUESTED)
