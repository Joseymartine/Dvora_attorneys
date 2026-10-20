# Dvora Attorneys

Django law firm management project. The initial Client model stores names,
contact details, and creation/update timestamps and is available in Django admin.

## Local setup

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
```

## PostgreSQL setup

Run the following in your terminal. `sudo` may ask for your Linux password.

```bash
sudo -u postgres psql
```

At the PostgreSQL prompt, create a dedicated login and database:

```sql
CREATE ROLE dvora_user WITH LOGIN;
\password dvora_user
CREATE DATABASE dvora_db OWNER dvora_user;
\q
```

The password command prompts for a new database password without putting it in
your shell history. If the role or database already exists, use the existing one.

```bash
cp .env.example .env
```

Edit `.env` and replace `DB_PASSWORD` with the database password you just chose.
Quote the value if it contains spaces or `#`. `.env` is excluded from Git.

```bash
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit http://127.0.0.1:8000/admin/ and sign in with your Django superuser to
create, view, update, and delete clients.

Without `.env`, the project continues to use its original SQLite database.
Switching to PostgreSQL creates a separate database; existing SQLite records
are not copied automatically. Run migrations again after switching databases.

## Current progress

- Completed: project/apps/homepage setup; Client model, initial migration, and admin registration.
- Prepared: PostgreSQL configuration through environment variables.
- PostgreSQL setup and migrations completed by the user.
- Completed: client list, detail, create, edit, and confirmed delete pages at `/clients/`.
  Access is restricted by role, model permissions, and case assignments.
- Completed: case CRUD, assignment restrictions, dedicated login/logout, and case role setup.
- Completed: client confidentiality and client role permissions.
- Completed: appointment CRUD, consultation requests, client login links, and scheduling checks.
- Completed: authenticated REST APIs for clients, cases, and appointments.
- Next: frontend styling and deployment preparation.

## Client CRUD

Run `python manage.py runserver` and open http://127.0.0.1:8000/clients/.
Unauthenticated visitors are sent to the dedicated login page.
The client list is paginated, forms validate required fields and email addresses,
and deletion requires a confirmation form submitted with a CSRF token.
Use `python manage.py test clients` to run the workflow and access tests.

## Case management

Apply migrations with `python manage.py migrate`, then run
`python manage.py setup_case_roles` to create the Administrators and Lawyers
groups and add case permissions. The command preserves existing permissions.
Use the superuser account at `/admin/` to create individual user accounts and
assign group membership. No test passwords or accounts are created automatically.

Open http://127.0.0.1:8000/cases/. The dedicated login is at `/accounts/login/`.
Superusers and Administrators with case permissions can create, view, edit, and
delete all cases. Active members of Lawyers are available for case assignment.
Lawyers can view and edit only their assigned cases, and can change only the
title, status, and description. They cannot create, delete, reassign, or change
the client or case number, even if granted extra case permissions. These rules
are enforced by the views, and unavailable actions are hidden in the templates.
The case interface in Django admin is restricted to superusers.

Cases protect linked clients and lawyers from deletion. Client deletion pages
show a validation message if cases still reference that client.
Case numbers are unique. Status choices are Open, In progress, On hold, and Closed.

Run `python manage.py test cases clients` for workflow and authorization tests.
The PostgreSQL test database requires the database role to have database-creation
rights; the implementation checks used a separate in-memory SQLite database.

## Client confidentiality

Run `python manage.py setup_client_roles` after migrations to add client
permissions to Administrators (view/add/change/delete) and Lawyers (view/change).
Existing group permissions are preserved. Staff status alone grants no client
access. Users need the appropriate group and model permission; superusers have
full access.

Administrators can manage all clients. Lawyers can list, view, and edit only
clients linked to a case currently assigned to them, including closed cases.
Multiple cases for a client do not duplicate list entries. Removing the lawyer's
last case assignment revokes client access on the next request. Lawyers cannot
create or delete clients, even if extra model permissions have been granted.
An inaccessible client returns 404 to avoid revealing whether it exists.

The client interface in Django admin is restricted to superusers, including
direct change URLs. Other users manage clients through `/clients/`.
No schema migration is needed for these authorization changes.

## Appointment management

Migrate with `python manage.py migrate`, then configure the role permissions with
`python manage.py setup_appointment_roles`. Existing permissions are preserved
except appointment-delete permission, which is removed from the managed groups.
Visit http://127.0.0.1:8000/appointments/ to manage appointments. All entered and
shown appointment times use Africa/Dar_es_Salaam (East Africa Time, UTC+3);
Django stores timezone-aware times. Existing timestamps retain their instants.

- Administrators: list, view, create, assign, reschedule, change status, and cancel
  any appointment, subject to model permissions.
- Lawyers: list, view, and update only their assigned appointments; cannot create,
  delete, reassign, or change the client. Staff status alone grants no access.
- Clients: request consultations and view only appointments for their own linked
  client record. They cannot edit, delete, assign lawyers, or confirm bookings,
  including through crafted POST data or extra model permissions.

### Enable a client login

1. Sign in as a superuser at `/admin/`.
2. Create a user under Users; add the account to the Clients group. Leave Staff
   status and Superuser status unchecked and Active checked.
3. Under Clients, open the matching client record, select that account in the
   optional User field, and save. One account can link to only one client.
4. The client signs in at `/accounts/login/`, opens Appointments, and selects
   Request consultation. Accounts without a linked client cannot submit requests.

The User link is editable only in the superuser admin, not ordinary client forms.
Existing client records do not need login accounts unless they request consultations.
No users, passwords, or links are created automatically.

Client submissions start as Requested without a lawyer. Administrators review
these requests and assign an active member of Lawyers, leaving the status as Requested.
The assigned lawyer opens the appointment and selects Approve appointment. The
client sees Confirmed in My appointments after approval. Administrators retain
the ability to manage appointment statuses. A
requested time is not guaranteed until confirmed. Status options are Requested,
Confirmed, Completed, and Cancelled. Notes are shared with the client; do not use
this field for internal notes. Client accounts are directed to appointments on
login; a valid explicit `next` destination is respected.

New or rescheduled start times must be in the future, and end times must follow
start times. Assigned Requested and Confirmed appointments block overlapping
slots for that lawyer; adjacent slots are allowed. Cancelled and Completed
appointments do not block slots. Booking writes recheck conflicts inside a
transaction while locking the lawyer row on PostgreSQL. Direct ORM writes must
perform equivalent validation; this is not a database exclusion constraint.
The appointment admin is read-only to avoid bypassing the scheduling flow.
Linked clients and assigned lawyers are protected against deletion.

Run `python manage.py test appointments clients cases` for the automated suite.
Implementation checks passed using a temporary in-memory SQLite database, which
does not verify PostgreSQL row-lock concurrency. No browser check was performed.

Permanent appointment deletion is disabled in the pages and Django admin.
Cancel through Edit → Status → Cancelled to retain history. The role setup
command removes appointment delete permission from its three managed groups.
See [the Phase 8 walkthrough](docs/appointment-management.md) for the code lesson.

## REST APIs (Phase 9)

Open http://127.0.0.1:8000/api/ after signing in. Clients, cases, and appointments
are available at `/api/clients/`, `/api/cases/`, and `/api/appointments/`.
The APIs reuse existing roles, model permissions, record filters, and appointment
validation. Session writes require CSRF protection. Lists are paginated at 20.
Cancel appointments with PATCH `{"status": "cancelled"}`; permanent deletion is
not supported. See [the REST API guide](docs/rest-api.md) for endpoint details,
role policies, JSON examples, a code walkthrough, and verification limits.
Run `python manage.py test api appointments clients cases` for the full suite.

## Website design

The public homepage, sign-in page, and management workspace share the firm's
navy, ivory, and gold identity. Start the server and visit `/` to see the new
homepage. Color tokens and responsive styles live in
`core/static/core/css/site.css`. See [the brand guide](docs/brand-style.md) for
hex codes, the color formula, typography, logo provenance, and editing guidance.
