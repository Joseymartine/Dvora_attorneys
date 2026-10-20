# Phase 8: Appointment Management walkthrough

The working module lives in `appointments/`. Follow this lesson with the listed
files open in your editor. The screenshots call a booked appointment Scheduled;
our existing implementation calls it Confirmed (stored as `confirmed`). Both
refer to a booking with an assigned lawyer. Requested supports the consultation
request feature already added; Completed and Cancelled retain appointment history.
The calendar image is inspiration for a later design phase; this module currently
uses list, detail, and form pages.

## 1. Understand the request flow

1. A browser requests `/appointments/`.
2. `config/urls.py` includes `appointments/urls.py`.
3. That file chooses the view for the URL.
4. The view checks login, role, model permissions, and allowed records.
5. On GET, the view renders a template. On POST, a form validates submitted data.
6. A valid form saves the model to PostgreSQL and redirects to the detail page.

The database persists records. Forms validate input. Views enforce access.
Templates display results. Hiding a button does not protect the underlying URL;
the view must enforce the same rule.

## 2. Model: appointments/models.py

Read this file from top to bottom:

- `from django.conf import settings` gives access to the project's user model setting.
- `ValidationError` lets validation report useful errors on a form.
- `models` supplies Django's database fields and model superclass.
- `Q` expresses a database condition; `F` refers to another column in the same row.
- `reverse` builds a URL from its name instead of hard-coding the address.
- `class Appointment(models.Model)` declares the table-backed Python class.
- `class Status(models.TextChoices)` defines allowed stored values and labels.
- Each status line contains a Python constant, database value, and display label.
  For example `CANCELLED = 'cancelled', 'Cancelled'` uses `cancelled` in PostgreSQL
  and displays Cancelled to the user.
- `title = models.CharField(max_length=200)` stores a required short description.
- `client = models.ForeignKey(...)` links many appointments to one client.
- `on_delete=models.PROTECT` prevents deleting a referenced client or lawyer.
- `related_name='appointments'` supports reverse lookups such as
  `client.appointments.all()`.
- `assigned_lawyer = models.ForeignKey(...)` links an appointment to a user.
- `settings.AUTH_USER_MODEL` respects Django's configured user model.
- `blank=True` allows an empty lawyer field in forms. `null=True` allows NULL
  in the database. Both support requests awaiting assignment.
- `limit_choices_to` limits the normal lawyer choices to active Lawyers group members.
  It does not replace the view's role and record checks.
- `starts_at` and `ends_at` store timezone-aware date and time values.
- `status` stores one of the allowed choices; new requests default to Requested.
- `notes` holds optional shared text. Its help text warns that clients can read it.
- `created_at` records the initial save; `updated_at` changes on subsequent saves.
- `class Meta` contains model configuration rather than appointment data.
- `ordering = ['starts_at', 'pk']` sorts chronologically, using the primary key
  to give appointments with identical start times a stable order.
- `CheckConstraint` requires `ends_at > starts_at` in the database. The `F`
  expression compares the end column with the start column for that same row.
- `__str__` returns the title when Python or Django displays an appointment.
- `get_absolute_url` uses `reverse('appointments:detail', args=[self.pk])` to
  return the detail URL of this saved record. CreateView and UpdateView use it
  after successful saves.
- `clean()` implements model validation. `super().clean()` preserves parent behavior.
- The first condition rejects an end time equal to or before the start time.
- The next condition requires a lawyer for Confirmed and Completed appointments.
- The early `return` skips overlap checks for missing times or inactive statuses.
- The final query searches for conflicting active appointments for that lawyer.
- `.exclude(pk=self.pk)` prevents an edited appointment conflicting with itself.
- `.exists()` asks whether at least one conflict exists without loading all rows.
- `raise ValidationError(...)` stops the save flow and shows the reason.

Django's `save()` does not automatically call `full_clean()`. Our forms and save
view perform validation. Scripts that write directly through the ORM must use
equivalent validation; the overlap rule is not a database exclusion constraint.

## 3. Understand overlap detection

The query checks these two comparisons together:

```python
existing.starts_at < proposed.ends_at
existing.ends_at > proposed.starts_at
```

For an existing 10:00–11:00 appointment with lawyer1:

| Proposed appointment | Result |
| --- | --- |
| 10:30–11:30, lawyer1 | Rejected: overlap |
| 09:30–10:30, lawyer1 | Rejected: overlap |
| 09:00–12:00, lawyer1 | Rejected: contains existing booking |
| 10:00–11:00, lawyer1 | Rejected: identical slot |
| 11:00–12:00, lawyer1 | Allowed: touches the end boundary |
| 10:30–11:30, lawyer2 | Allowed: different lawyer |

Assigned Requested and Confirmed appointments block the lawyer's schedule.
Cancelled and Completed appointments do not. Unassigned requests reserve no
lawyer's time; the conflict check runs when an administrator assigns the lawyer.

## 4. Forms: appointments/forms.py

`ScheduleForm(forms.ModelForm)` builds form fields from the Appointment model.
Its `Meta.model` selects the model and `Meta.fields` explicitly lists editable
fields. That list is also a security boundary: extra POST fields are not saved.
The notes widget displays a multi-line text area.

`__init__` calls the parent initializer, remembers the original start, and replaces
the two time widgets with browser `datetime-local` inputs. The format and
`input_formats` tell Django how to render and parse values such as
`2026-10-22T10:00`. These values are interpreted in Africa/Dar_es_Salaam.

`clean_starts_at` validates that a new or changed start time is in the future.
The `original_start` comparison allows editing notes or cancelling an existing
past appointment without changing its historical time. `timezone.now()` is aware
of time zones. The cleaned value is returned for later model validation.

The three forms expose different fields:

| Form | Editable fields |
| --- | --- |
| ScheduleForm | Title, client, lawyer, times, status, notes |
| LawyerScheduleForm | Title, times, status, notes |
| ConsultationRequestForm | Title, times, notes |

The lawyer form cannot change the client or lawyer. The request form cannot
choose a client, lawyer, or status. Those values are supplied by the view.

## 5. Permissions and record filtering: appointments/views.py

`is_lawyer(user)` checks Lawyers group membership. `linked_client(user)` retrieves
the client record explicitly connected to the account. It never matches by an
unverified email address.

`AppointmentAccessMixin` combines shared checks:

- `LoginRequiredMixin` sends anonymous visitors to the login page.
- `PermissionRequiredMixin` checks the permissions listed by each view.
- `model = Appointment` tells the generic views which model to use.
- `has_permission()` also requires an allowed role. Clients need both Clients
  group membership and an explicitly linked client record.
- `get_queryset()` determines which database records this request may retrieve.
  Administrators receive all records, lawyers only their assignments, and
  clients only records belonging to their linked client profile.
- `select_related` fetches the client and lawyer in the same query, avoiding
  repeated lookups while rendering the list.
- `get_context_data()` adds flags to control which actions the templates display.

A lawyer guessing another lawyer's appointment ID receives 404 because the
record is outside their allowed queryset. A signed-in user without the required
operation permission receives 403.

`SaveAppointmentMixin.form_valid` controls the save:

1. `transaction.atomic()` groups the work into one transaction.
2. `select_for_update()` locks the assigned lawyer's user row on PostgreSQL,
   serializing booking saves that use this same lock.
3. `full_clean()` rechecks the complete model inside the lock, including overlaps.
4. Validation errors are added to the form; the record is not saved.
5. The shared `save_appointment` service saves inside the transaction, and
   `HttpResponseRedirect(self.get_success_url())` redirects after success.
6. A success message is displayed after the save transaction finishes.

The tests using SQLite do not verify PostgreSQL locking behavior.

The concrete views are short because generic views supply the standard workflow:

| View | Responsibility |
| --- | --- |
| AppointmentListView | View permission; allowed appointments, 20 per page |
| AppointmentDetailView | View permission; one allowed appointment |
| AppointmentCreateView | Add and view permissions; administrator or linked client |
| AppointmentUpdateView | Change and view permissions; administrator or assigned lawyer |

CreateView chooses the administrator form or request form. For client requests,
`form_valid` explicitly sets the linked client, Requested status, and no lawyer.
Forging these fields in POST cannot change them.

UpdateView chooses the administrator or lawyer form. Queryset filtering still
runs before selecting a record to edit. Clients cannot edit appointments, even
if someone accidentally grants them a change permission.

There is no permanent-delete view or URL. Django admin is read-only for
appointments and also rejects deletion. To cancel, use Edit, select Cancelled,
and save. This preserves the row and frees the lawyer's time slot.

## 6. URLs and templates

`config/urls.py` includes the appointment URLs under `/appointments/`.
`app_name = 'appointments'` gives route names a namespace to avoid collisions.

- `''` opens the list.
- `'add/'` opens the create/request form.
- `'<int:pk>/'` opens a detail page. `pk` is the database primary key.
- `'<int:pk>/edit/'` opens the appropriate edit form.
- `name=` lets templates and Python build links with reverse lookup.

Each appointment template extends `clients/base.html`, reusing the existing
navigation, styles, messages, and page structure.

- `{% block title %}` and `{% block content %}` fill the base template's slots.
- `{% if %}` displays actions appropriate to this user's permissions and role.
- `{% for %}` displays one table row per allowed appointment.
- `{{ appointment.title }}` displays data with Django's normal HTML escaping.
- `{% url 'appointments:update' object.pk %}` builds the edit URL.
- `{{ form.as_p }}` renders labels, fields, help text, and validation errors.
- `method="post"` sends a state-changing form submission.
- `{% csrf_token %}` adds Django's request-forgery protection token.
- The pagination links use `?page=` to request another page of allowed records.
- The date filter formats timezone-local values for readable display.

The browser's Cancel link leaves an unsaved form. Appointment cancellation is
separate: choose the Cancelled status and save.

## 7. Migrations and roles

The following commands have already been applied to this project's PostgreSQL
database. On another installation, activate its environment and run:

```bash
python manage.py migrate
python manage.py setup_appointment_roles
```

The migrations create the Appointment table and add the optional `Client.user`
one-to-one link. The role command adds view/add/change permissions to
Administrators, view/change to Lawyers, and view/add to Clients. It removes
appointment delete permission from those three groups to match this phase.
Other existing permissions are preserved.

Django automatically defines model permissions during migration. A permission
existing in the database does not make an action available: an exposed view and
its checks are still required.

## 8. Tests: appointments/tests.py

`TestCase` runs each test against isolated database state. `setUpTestData` creates
users, groups, clients, and bookings for the class. The `data()` helper supplies
valid local-time form values using dates relative to the test run.

- `force_login()` signs in a test user without testing the login form itself.
- `self.client.get()` requests a page; `post()` submits a form.
- `assertRedirects()` checks the destination after a successful operation.
- `assertContains()` checks rendered output and HTTP status.
- `refresh_from_db()` reloads a row before checking persisted changes.
- `subTest()` reports which invalid-input example failed.
- `Browser(enforce_csrf_checks=True)` enables CSRF verification for that test.

The suite covers creation and updates, cancellation retaining the row, all roles
being denied permanent deletion, lawyer and client record isolation, forged
assignments, invalid dates, overlap rejection, adjacent slots, cancelled slots,
login routing, CSRF, and protected client/lawyer relationships.

```bash
python manage.py test appointments clients cases
```

Django's PostgreSQL test runner creates a separate test database. The database
user needs permission to create that database; do not run tests against the
ordinary development database by replacing its name manually.

## 9. Try the workflow yourself

1. Open `/appointments/` as the administrator. Create a future appointment with
   a client, active lawyer, and Confirmed status.
2. Attempt an overlapping booking for the same lawyer. Expect a form error.
3. Try a booking starting exactly when the first ends. Expect success.
4. Sign in as the assigned lawyer. Open and edit that appointment.
5. Sign in as a different lawyer. The appointment should be absent; its direct
   detail URL should return 404.
6. As the assigned lawyer or administrator, select Cancelled and save. The
   appointment must remain listed with Cancelled status.
7. Book its original time slot again. Cancellation should have freed that slot.
8. To test requests, create a user in Clients and link it through the User field
   of the correct client in superuser admin. Sign in as that user and request a
   consultation. It should remain Requested until an administrator assigns and
   confirms it. Another client must not see that request.
