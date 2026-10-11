import datetime
from io import StringIO
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from core.models import Service
from doctors.models import Doctor, DoctorTimeOff

IST = ZoneInfo('Asia/Kolkata')
PASSWORD = 'Demo@12345'
BASE = '/api/v1'


def future_weekday(days_ahead=3, weekday_max=4):
    """A Mon-Fri date at least `days_ahead` days from now."""
    day = timezone.now().astimezone(IST).date() + datetime.timedelta(days=days_ahead)
    while day.weekday() > weekday_max:
        day += datetime.timedelta(days=1)
    return day


def at(day, hour, minute=0):
    return datetime.datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)


class ApiTestBase(APITestCase):
    def setUp(self):
        cache.clear()  # reset the login rate-limit counter between tests

    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0, stdout=StringIO())
        cls.arjun = Doctor.objects.get(slug='dr-arjun-mehta')
        cls.neha = Doctor.objects.get(slug='dr-neha-kapoor')
        cls.rehab = Service.objects.get(slug='sports-injury-rehab-session')      # 30 min
        cls.assessment = Service.objects.get(slug='initial-assessment')           # 45 min

    def login(self, email):
        self.client.credentials()
        res = self.client.post(f'{BASE}/auth/login/', {'email': email, 'password': PASSWORD}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return res.data

    def as_patient(self):
        return self.login('patient@physioconnect.demo')

    def as_arjun(self):
        return self.login('arjun.mehta@physioconnect.demo')

    def as_neha(self):
        return self.login('neha.kapoor@physioconnect.demo')

    def as_reception(self):
        return self.login('reception@physioconnect.demo')

    def book(self, doctor=None, service=None, start=None, **extra):
        doctor, service = doctor or self.arjun, service or self.rehab
        start = start or at(future_weekday(), 9)
        payload = {'doctor': str(doctor.id), 'service': service.id, 'scheduled_start': start.isoformat(), **extra}
        return self.client.post(f'{BASE}/appointments/', payload, format='json')


class AuthTests(ApiTestBase):
    def test_register_login_and_me(self):
        res = self.client.post(f'{BASE}/auth/register/', {
            'email': 'new.user@example.com', 'password': 'Str0ng!Pass99', 'first_name': 'New', 'last_name': 'User',
            'phone': '9000000001'}, format='json')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data['user']['role'], 'patient')
        self.assertIsNotNone(res.data['user']['patient_id'])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        me = self.client.get(f'{BASE}/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['email'], 'new.user@example.com')

    def test_duplicate_email_rejected(self):
        res = self.client.post(f'{BASE}/auth/register/', {
            'email': 'patient@physioconnect.demo', 'password': 'Str0ng!Pass99',
            'first_name': 'A', 'last_name': 'B'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['error']['code'], 'VALIDATION_ERROR')

    def test_wrong_password(self):
        res = self.client.post(f'{BASE}/auth/login/', {'email': 'patient@physioconnect.demo', 'password': 'nope'},
                               format='json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data['error']['code'], 'INVALID_CREDENTIALS')

    def test_login_by_phone(self):
        res = self.client.post(f'{BASE}/auth/login/', {'identifier': '9876500001', 'password': PASSWORD},
                               format='json')
        self.assertEqual(res.status_code, 200)

    def test_protected_endpoint_needs_login(self):
        res = self.client.get(f'{BASE}/appointments/')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data['error']['code'], 'NOT_AUTHENTICATED')

    def test_refresh_token(self):
        data = self.as_patient()
        self.client.credentials()
        res = self.client.post(f'{BASE}/auth/refresh/', {'refresh': data['refresh']}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)


class PublicCatalogTests(ApiTestBase):
    def test_doctors_and_services_are_public(self):
        doctors = self.client.get(f'{BASE}/doctors/')
        self.assertEqual(doctors.status_code, 200)
        self.assertEqual(len(doctors.data), 2)
        self.assertTrue(doctors.data[0]['services'])
        self.assertEqual(self.client.get(f'{BASE}/services/').status_code, 200)

    def test_doctor_detail_by_slug_shows_weekly_hours(self):
        res = self.client.get(f'{BASE}/doctors/dr-arjun-mehta/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['weekly_availability']), 6)

    def test_slots_follow_working_hours_and_service_length(self):
        day = future_weekday()
        res = self.client.get(f'{BASE}/doctors/{self.arjun.id}/available-slots/',
                              {'date': day.isoformat(), 'service_id': self.rehab.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['slots']), 16)            # 09:00-17:00 in 30-min steps
        res45 = self.client.get(f'{BASE}/doctors/{self.arjun.id}/available-slots/',
                                {'date': day.isoformat(), 'service_id': self.assessment.id})
        self.assertEqual(len(res45.data['slots']), 15)          # last 45-min start is 16:00 (16:30 would end 17:15)

    def test_no_slots_on_sunday(self):
        day = future_weekday()
        while day.weekday() != 6:
            day += datetime.timedelta(days=1)
        res = self.client.get(f'{BASE}/doctors/{self.arjun.id}/available-slots/',
                              {'date': day.isoformat(), 'service_id': self.rehab.id})
        self.assertEqual(res.data['slots'], [])

    def test_doctor_time_off_removes_slots(self):
        day = future_weekday()
        DoctorTimeOff.objects.create(doctor=self.arjun, start_datetime=at(day, 9), end_datetime=at(day, 12))
        res = self.client.get(f'{BASE}/doctors/{self.arjun.id}/available-slots/',
                              {'date': day.isoformat(), 'service_id': self.rehab.id})
        self.assertEqual(len(res.data['slots']), 10)

    def test_service_the_doctor_does_not_offer(self):
        back = Service.objects.get(slug='back-neck-pain-therapy')
        res = self.client.get(f'{BASE}/doctors/{self.arjun.id}/available-slots/',
                              {'date': future_weekday().isoformat(), 'service_id': back.id})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data['error']['code'], 'SERVICE_NOT_OFFERED')

    def test_bad_date(self):
        res = self.client.get(f'{BASE}/doctors/{self.arjun.id}/available-slots/', {'date': 'tomorrow', 'service_id': 1})
        self.assertEqual(res.status_code, 400)


class BookingTests(ApiTestBase):
    def test_patient_books_and_invoice_is_created(self):
        self.as_patient()
        res = self.book()
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data['status'], 'confirmed')
        self.assertEqual(res.data['patient']['name'], 'Priya Sharma')
        self.assertEqual(res.data['invoice']['total'], '800.00')
        self.assertTrue(res.data['invoice']['invoice_number'].startswith('INV-'))
        start = datetime.datetime.fromisoformat(res.data['scheduled_start'].replace('Z', '+00:00'))
        end = datetime.datetime.fromisoformat(res.data['scheduled_end'].replace('Z', '+00:00'))
        self.assertEqual(end - start, datetime.timedelta(minutes=30))

    def test_same_slot_twice_is_409(self):
        self.as_patient()
        self.assertEqual(self.book().status_code, 201)
        second = self.book()
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data['error']['code'], 'SLOT_TAKEN')

    def test_overlapping_longer_visit_is_blocked(self):
        """A 45-min visit at 9:00 covers the 9:30 slot, so 9:30 must be refused."""
        self.as_patient()
        self.assertEqual(self.book(service=self.assessment, start=at(future_weekday(), 9)).status_code, 201)
        res = self.book(start=at(future_weekday(), 9, 30))
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data['error']['code'], 'SLOT_TAKEN')

    def test_booked_slot_disappears_from_availability(self):
        self.as_patient()
        day = future_weekday()
        self.book(start=at(day, 9))
        res = self.client.get(f'{BASE}/doctors/{self.arjun.id}/available-slots/',
                              {'date': day.isoformat(), 'service_id': self.rehab.id})
        self.assertEqual(len(res.data['slots']), 15)

    def test_outside_working_hours_is_422(self):
        self.as_patient()
        res = self.book(start=at(future_weekday(), 20))
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data['error']['code'], 'INVALID_SLOT')

    def test_past_time_is_422(self):
        self.as_patient()
        res = self.book(start=at(timezone.now().astimezone(IST).date() - datetime.timedelta(days=2), 9))
        self.assertEqual(res.status_code, 422)

    def test_not_logged_in_cannot_book(self):
        self.assertEqual(self.book().status_code, 401)

    def test_doctor_cannot_book(self):
        self.as_arjun()
        self.assertEqual(self.book().status_code, 403)

    def test_service_doctor_does_not_offer(self):
        self.as_patient()
        back = Service.objects.get(slug='back-neck-pain-therapy')
        res = self.book(service=back)
        self.assertEqual(res.status_code, 422)

    def test_cancelled_slot_can_be_rebooked(self):
        self.as_patient()
        appt = self.book().data
        self.assertEqual(self.client.post(f"{BASE}/appointments/{appt['id']}/cancel/", {'reason': 'Unwell'},
                                          format='json').status_code, 200)
        self.assertEqual(self.book().status_code, 201)


class ChangeBookingTests(ApiTestBase):
    def test_patient_cancel_and_reschedule(self):
        self.as_patient()
        day = future_weekday()
        appt = self.book(start=at(day, 10)).data

        moved = self.client.post(f"{BASE}/appointments/{appt['id']}/reschedule/",
                                 {'scheduled_start': at(day, 11).isoformat()}, format='json')
        self.assertEqual(moved.status_code, 200, moved.content)

        cancelled = self.client.post(f"{BASE}/appointments/{appt['id']}/cancel/", {'reason': 'Travelling'},
                                     format='json')
        self.assertEqual(cancelled.data['status'], 'cancelled')
        again = self.client.post(f"{BASE}/appointments/{appt['id']}/cancel/", {}, format='json')
        self.assertEqual(again.status_code, 422)
        self.assertEqual(again.data['error']['code'], 'INVALID_STATE')

    def test_reschedule_into_taken_slot_is_409(self):
        self.as_patient()
        day = future_weekday()
        self.book(start=at(day, 10))
        other = self.book(start=at(day, 11)).data
        res = self.client.post(f"{BASE}/appointments/{other['id']}/reschedule/",
                               {'scheduled_start': at(day, 10).isoformat()}, format='json')
        self.assertEqual(res.status_code, 409)

    def test_patient_cannot_cancel_inside_window_but_staff_can(self):
        self.as_patient()
        appt = self.book().data
        from appointments.models import Appointment
        Appointment.objects.filter(pk=appt['id']).update(
            scheduled_start=timezone.now() + datetime.timedelta(hours=1),
            scheduled_end=timezone.now() + datetime.timedelta(hours=1, minutes=30))
        res = self.client.post(f"{BASE}/appointments/{appt['id']}/cancel/", {}, format='json')
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data['error']['code'], 'CANCELLATION_WINDOW_PASSED')

        self.as_reception()
        self.assertEqual(self.client.post(f"{BASE}/appointments/{appt['id']}/cancel/", {'reason': 'Called in'},
                                          format='json').status_code, 200)


class VisitFlowAndNotesTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.as_patient()
        self.appt = self.book().data
        self.url = f"{BASE}/appointments/{self.appt['id']}"

    def test_full_visit_flow(self):
        self.as_reception()
        self.assertEqual(self.client.post(f'{self.url}/check-in/').data['status'], 'checked_in')
        self.as_arjun()
        self.assertEqual(self.client.post(f'{self.url}/start/').data['status'], 'in_progress')
        self.assertEqual(self.client.post(f'{self.url}/complete/').data['status'], 'completed')
        self.assertEqual(self.client.post(f'{self.url}/start/').status_code, 422)   # cannot go backwards

    def test_wrong_roles_cannot_move_status(self):
        self.as_patient()
        self.assertEqual(self.client.post(f'{self.url}/check-in/').status_code, 403)
        self.as_reception()
        self.assertEqual(self.client.post(f'{self.url}/complete/').status_code, 403)

    def test_no_show(self):
        self.as_reception()
        self.assertEqual(self.client.post(f'{self.url}/no-show/').data['status'], 'no_show')

    def test_doctor_writes_notes_and_sees_history(self):
        self.as_reception()
        self.client.post(f'{self.url}/check-in/')
        self.as_arjun()
        saved = self.client.put(f'{self.url}/notes/', {
            'subjective': 'Knee pain after running', 'objective': 'Swelling, limited flexion',
            'assessment': 'Mild ligament strain', 'plan': 'Rest, ice, strengthening'}, format='json')
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(self.client.get(f'{self.url}/notes/').data['assessment'], 'Mild ligament strain')

        history = self.client.get(f"{BASE}/patients/{self.appt['patient']['id']}/history/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data['visits'][0]['notes']['plan'], 'Rest, ice, strengthening')

    def test_notes_are_private_to_doctors(self):
        for login in (self.as_patient, self.as_reception):
            login()
            self.assertEqual(self.client.get(f'{self.url}/notes/').status_code, 403)

    def test_notes_refused_before_check_in(self):
        self.as_arjun()
        self.assertEqual(self.client.put(f'{self.url}/notes/', {'plan': 'x'}, format='json').status_code, 422)

    def test_other_doctor_cannot_see_appointment(self):
        self.as_neha()
        self.assertEqual(self.client.get(self.url + '/').status_code, 404)
        self.assertEqual(self.client.get(f'{BASE}/appointments/').data['count'], 0)

    def test_reception_history_has_no_clinical_notes(self):
        self.as_reception()
        history = self.client.get(f"{BASE}/patients/{self.appt['patient']['id']}/history/")
        self.assertNotIn('notes', history.data['visits'][0])


class PrivacyTests(ApiTestBase):
    def test_patient_cannot_see_someone_elses_appointment(self):
        self.as_patient()
        appt = self.book().data
        self.client.post(f'{BASE}/auth/register/', {
            'email': 'other@example.com', 'password': 'Str0ng!Pass99', 'first_name': 'Other', 'last_name': 'Person'},
            format='json')
        self.client.credentials()
        res = self.client.post(f'{BASE}/auth/login/', {'email': 'other@example.com', 'password': 'Str0ng!Pass99'},
                               format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.assertEqual(self.client.get(f"{BASE}/appointments/{appt['id']}/").status_code, 404)
        self.assertEqual(self.client.get(f'{BASE}/appointments/').data['count'], 0)
        self.assertEqual(self.client.get(f"{BASE}/patients/{appt['patient']['id']}/").status_code, 404)

    def test_patient_cannot_list_patients(self):
        self.as_patient()
        self.assertEqual(self.client.get(f'{BASE}/patients/').status_code, 403)


class FrontDeskAndPaymentTests(ApiTestBase):
    def test_receptionist_registers_walk_in_and_books_for_them(self):
        self.as_reception()
        patient = self.client.post(f'{BASE}/patients/', {
            'first_name': 'Ravi', 'last_name': 'Kumar', 'phone': '9811122233'}, format='json')
        self.assertEqual(patient.status_code, 201, patient.content)
        dup = self.client.post(f'{BASE}/patients/', {
            'first_name': 'Ravi', 'last_name': 'Kumar', 'phone': '9811122233'}, format='json')
        self.assertEqual(dup.status_code, 400)

        res = self.book(patient=patient.data['id'], booking_channel='walk_in')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data['booking_channel'], 'walk_in')
        self.assertEqual(self.client.get(f"{BASE}/patients/?q=9811").data['count'], 1)

    def test_staff_booking_needs_patient(self):
        self.as_reception()
        self.assertEqual(self.book().status_code, 400)

    def test_manual_payment_partial_then_full(self):
        self.as_patient()
        appt = self.book().data
        invoice_id = appt['invoice']['id']

        self.assertEqual(self.client.post(f'{BASE}/invoices/{invoice_id}/manual-payment/',
                                          {'amount': '100', 'method': 'cash'}, format='json').status_code, 403)

        self.as_reception()
        part = self.client.post(f'{BASE}/invoices/{invoice_id}/manual-payment/',
                                {'amount': '300.00', 'method': 'cash'}, format='json')
        self.assertEqual(part.status_code, 201, part.content)
        self.assertEqual(part.data['status'], 'partially_paid')
        self.assertEqual(part.data['amount_due'], '500.00')

        over = self.client.post(f'{BASE}/invoices/{invoice_id}/manual-payment/',
                                {'amount': '600.00', 'method': 'upi'}, format='json')
        self.assertEqual(over.status_code, 422)
        self.assertEqual(over.data['error']['code'], 'OVERPAYMENT')

        full = self.client.post(f'{BASE}/invoices/{invoice_id}/manual-payment/',
                                {'amount': '500.00', 'method': 'upi'}, format='json')
        self.assertEqual(full.data['status'], 'paid')
        self.assertEqual(full.data['amount_due'], '0.00')
        again = self.client.post(f'{BASE}/invoices/{invoice_id}/manual-payment/',
                                 {'amount': '1.00', 'method': 'cash'}, format='json')
        self.assertEqual(again.data['error']['code'], 'ALREADY_PAID')

    def test_patient_sees_own_invoices_doctor_sees_none(self):
        self.as_patient()
        self.book()
        self.assertEqual(self.client.get(f'{BASE}/invoices/').data['count'], 1)
        self.as_arjun()
        self.assertEqual(self.client.get(f'{BASE}/invoices/').data['count'], 0)

    def test_dashboards(self):
        self.as_patient()
        self.book()
        self.assertEqual(self.client.get(f'{BASE}/dashboard/').data['upcoming_count'], 1)
        self.as_reception()
        data = self.client.get(f'{BASE}/dashboard/').data
        self.assertEqual(data['role'], 'receptionist')
        self.assertEqual(data['outstanding_invoices'], 1)
        self.as_arjun()
        self.assertEqual(self.client.get(f'{BASE}/dashboard/').data['role'], 'doctor')

    def test_medical_profile_access(self):
        self.as_patient()
        appt = self.book().data
        pid = appt['patient']['id']
        self.as_arjun()
        saved = self.client.patch(f'{BASE}/patients/{pid}/medical-profile/',
                                  {'allergies': ['penicillin']}, format='json')
        self.assertEqual(saved.status_code, 200)
        self.as_reception()
        self.assertEqual(self.client.get(f'{BASE}/patients/{pid}/medical-profile/').status_code, 403)
