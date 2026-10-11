# PhysioConnect - Backend

Django REST API for a physiotherapy clinic: patients, doctors, booking, visit
notes and front-desk payments.

## Run it (Windows PowerShell, from the folder that contains manage.py)

```
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

API: http://127.0.0.1:8000/api/v1/    Admin: http://127.0.0.1:8000/admin/

`seed_demo` creates demo logins (password for all: `Demo@12345`):
`arjun.mehta@physioconnect.demo`, `neha.kapoor@physioconnect.demo` (doctors),
`reception@physioconnect.demo`, `patient@physioconnect.demo`.

Run the automated checks any time: `python manage.py test` (should end with OK).

## Endpoints (all under /api/v1/)

Public: `services/`, `clinic/`, `doctors/`, `doctors/<slug-or-id>/`,
`doctors/<id>/available-slots/?date=YYYY-MM-DD&service_id=N`,
`auth/register/`, `auth/login/`, `auth/refresh/`
Logged in: `auth/me/`, `dashboard/`

| Endpoint | Who |
|---|---|
| `GET/POST appointments/` | patient (own), doctor (own), receptionist/admin (all; can book for a patient) |
| `GET appointments/<id>/` | same visibility rules |
| `POST appointments/<id>/cancel/` and `reschedule/` | patient (outside cancellation window), receptionist, doctor, admin |
| `POST appointments/<id>/check-in/` | receptionist, admin |
| `POST appointments/<id>/start/` and `complete/` | doctor, admin |
| `POST appointments/<id>/no-show/` | receptionist, doctor, admin |
| `GET/PUT appointments/<id>/notes/` (SOAP notes) | doctor, admin |
| `GET/POST patients/` (POST registers a walk-in) | doctor / receptionist / admin |
| `GET/PATCH patients/<id>/` | patient (self), receptionist, admin; doctor read-only |
| `GET patients/<id>/history/` | clinical notes included for doctor/admin only |
| `GET/PATCH patients/<id>/medical-profile/` | doctor, admin (patient may read own) |
| `GET invoices/`, `GET invoices/<id>/` | patient (own), receptionist, admin |
| `POST invoices/<id>/manual-payment/` `{amount, method: cash/upi/pos_card/other}` | receptionist, admin |

Send the login token as `Authorization: Bearer <access token>`.
Errors always look like `{"error": {"code": "SLOT_TAKEN", "message": "...", "details": {}}}`.

## Not built yet
Online Razorpay payments, email/SMS reminders, exercise plans API, CMS/blog API,
reports, password reset, OTP login.

## Before going live
Set a real `SECRET_KEY`, `DEBUG=False` and `ALLOWED_HOSTS` in a `.env` file
(see `.env.example`), move to PostgreSQL, and set your real GST rate in
Admin > Clinic Settings. Row-locking during booking is fully effective on
PostgreSQL; SQLite is for development only.
