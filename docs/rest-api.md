# Phase 9: REST APIs

## Verification completed before implementation

The pre-API suite passed 36 tests, including appointment list, detail, and form
rendering, East Africa Time values, overlapping-slot rejection, and adjacent-slot
acceptance. After API implementation, the combined suite passed 50 tests using
an isolated in-memory SQLite database.

A separate PostgreSQL smoke check rendered appointment list/detail HTML, read and
updated a booking through the API, rejected an overlap through the shared save
service, and cancelled without deleting. All smoke-check records were rolled
back. These checks do not replace visual browser QA or a concurrent PostgreSQL
booking test.

## Start and sign in

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
python manage.py runserver
```

Open http://127.0.0.1:8000/api/ in your browser. Sign in through the browsable
API's Login link at `/api-auth/login/` or the existing `/accounts/login/` page.
Existing users, groups, and model permissions are reused. No new users, tokens,
or permissions are created by this API layer.

The API uses Django session authentication. Anonymous requests receive 403,
as is normal for SessionAuthentication. Writes require a session plus a valid
CSRF token. No Basic, token, or JWT authentication is enabled in this phase.

## Endpoints

| Collection | Detail | Allowed methods |
| --- | --- | --- |
| `/api/clients/` | `/api/clients/{id}/` | GET/POST on collection; GET/PUT/PATCH/DELETE on detail |
| `/api/cases/` | `/api/cases/{id}/` | GET/POST on collection; GET/PUT/PATCH/DELETE on detail |
| `/api/appointments/` | `/api/appointments/{id}/` | GET/POST on collection; GET/PUT/PATCH on detail |

Permissions restrict these methods by role. Appointment DELETE is not supported
(405 for users with read access). Cancel using PATCH with `status: cancelled`.
Collections return `count`, `next`, `previous`, and `results`, with 20 records per
page. Use `?page=2` for the next page. IDs are ordinary integer primary keys.

## Access policy

Administrators with the required model permissions manage all client and case
records and all appointments. Superusers satisfy these role/permission checks.
Plain staff status does not grant API access.

Lawyers need the corresponding view/change model permissions. They can:

- Read/update clients connected to their assigned cases.
- Read/update only their assigned cases; write title, status, and description.
- Read/update only their assigned appointments; write title, starts_at, ends_at,
  status, and notes. They can cancel an assigned appointment.

Lawyers cannot create/delete records or change case/appointment assignments,
client links, case numbers, or date opened. Extra model permissions do not
bypass the role rules. Requesting an inaccessible record returns 404; lacking
an operation permission returns 403.

Clients need Clients group membership, view/add appointment permissions, and an
explicit client-account link. They can request consultations and read only their
own appointments. They cannot read the client or case APIs or update bookings.
A consultation request accepts only title, starts_at, ends_at, and notes. Client,
assigned_lawyer, and status are set by the server. Supplying those fields returns
400 rather than changing identity or confirming a request.

Client-account links are managed only in superuser admin. The client serializer
never returns `user`, and rejects attempts to set that field through the API.
Records containing client or case relationships are represented by IDs rather
than embedded unrelated private records. Non-administrator relationship fields
are read-only and do not offer a dropdown of other clients/lawyers.

## JSON examples

Use actual IDs from your administrator account. Model values match the existing
web application. Send date-times as ISO 8601 with an explicit time-zone offset.

Create a client as an administrator with POST `/api/clients/`:

```json
{
  "first_name": "Amina",
  "last_name": "Example",
  "email": "amina@example.com",
  "phone": "+255700000000",
  "address": "Dar es Salaam"
}
```

Create a case as an administrator with POST `/api/cases/`:

```json
{
  "case_number": "DV-2026-001",
  "title": "Property consultation",
  "client": 1,
  "assigned_lawyer": 2,
  "status": "open",
  "date_opened": "2026-10-19",
  "description": "Initial case summary"
}
```

Create a confirmed appointment as an administrator with POST `/api/appointments/`.
Choose future dates at the time you run the example:

```json
{
  "title": "Property consultation",
  "client": 1,
  "assigned_lawyer": 2,
  "starts_at": "2026-10-22T10:00:00+03:00",
  "ends_at": "2026-10-22T11:00:00+03:00",
  "status": "confirmed",
  "notes": "Shared with the client"
}
```

As a linked client, omit client, assigned_lawyer, and status when POSTing a
consultation request. The response identifies the linked client, has a null
lawyer, and uses Requested status.

Cancel with PATCH `/api/appointments/1/` as an administrator or assigned lawyer:

```json
{"status": "cancelled"}
```

PATCH changes only supplied fields. PUT is the full-update method and requires
all required writable fields for that user's serializer. Restricted fields
submitted by lawyers/clients return a field-specific 400 response. Read-only
IDs and timestamps cannot be edited.

## Browser JavaScript example

Sign in and open the browsable API first so the CSRF cookie is set. Run this
from the same origin, using an appointment you are allowed to change:

```javascript
const csrfToken = document.cookie.split('; ')
  .find(value => value.startsWith('csrftoken='))?.split('=')[1];
const response = await fetch('/api/appointments/1/', {
  method: 'PATCH',
  credentials: 'same-origin',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': decodeURIComponent(csrfToken || '')
  },
  body: JSON.stringify({status: 'cancelled'})
});
console.log(response.status, await response.json());
```

## Validation and status codes

- 200: read or update succeeded.
- 201: a new record was created.
- 204: an allowed client/case deletion succeeded.
- 400: invalid fields, duplicate case number, protected deletion, or scheduling conflict.
- 403: authentication/permission failure or missing CSRF token on a session write.
- 404: missing record or record outside the user's accessible queryset.
- 405: unsupported method, including appointment deletion for an authorized reader.

Appointment validation checks future start times for new/rescheduled bookings,
positive duration, active lawyer membership, valid statuses, and required lawyer
assignment for Confirmed/Completed appointments. PATCH is validated against the
existing unsupplied fields too. Overlapping Requested/Confirmed bookings for a
lawyer are rejected, adjacent slots are allowed, and Cancelled/Completed slots
are released. Cancelling preserves the appointment row.

Both HTML and API saves call `appointments/services.py:save_appointment`, which
locks the lawyer row and revalidates inside a transaction. HTML and API queries
share the record filters in `core/access.py`. Direct ORM/database writes remain
outside this application-level policy; a database overlap exclusion constraint,
audit logging, and PostgreSQL concurrency tests remain separate future work.

## Code walkthrough

1. `config/settings.py` installs DRF, requires authentication by default, chooses
   session authentication, and sets page size.
2. `api/urls.py` registers three viewsets on DefaultRouter. The router builds
   collection/detail URLs and the browsable API index.
3. `api/permissions.py` requires an active authenticated user, view permission
   plus the action's model permission, and the existing role policy.
4. `core/access.py` filters querysets. Generic views retrieve objects from these
   filtered querysets, protecting both lists and guessed detail URLs.
5. `api/serializers.py` declares explicit JSON fields, writable relationship
   choices, role-specific restrictions, and model validation. Validation uses
   a copy of the existing record so PATCH can check the complete proposed state.
6. `api/views.py` supplies scoped viewsets. Protected client deletion becomes a
   400 error, rather than a database error. Appointments omit DestroyModelMixin
   so no permanent-delete operation exists.
7. `appointments/services.py` provides the shared transaction and overlap check.
8. `api/tests.py` tests the endpoint workflows and negative authorization paths.

## Tests

```bash
python manage.py test api appointments clients cases
```

The PostgreSQL test runner requires permission to create a separate test database.
The implementation suite used in-memory SQLite; the PostgreSQL smoke check used
rollback-only temporary data. Session CSRF is tested without bypassing the CSRF
check; ordinary endpoint tests use forced authentication to focus on authorization.

Official references:
[Django REST Framework permissions](https://www.django-rest-framework.org/api-guide/permissions/),
[serializers](https://www.django-rest-framework.org/api-guide/serializers/),
[viewsets](https://www.django-rest-framework.org/api-guide/viewsets/).
