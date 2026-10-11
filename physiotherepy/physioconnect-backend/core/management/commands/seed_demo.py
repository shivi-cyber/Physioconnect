"""python manage.py seed_demo

Creates everything needed to try the system in one go: roles, clinic settings,
services, two doctors with weekly hours, a receptionist and a demo patient.
Safe to run more than once.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Role
from core.models import ClinicSettings, Service, ServiceCategory
from doctors.models import Doctor, DoctorAvailability, DoctorService, Specialization
from patients.models import Patient

User = get_user_model()
DEMO_PASSWORD = 'Demo@12345'

SERVICES = [
    ('Initial Assessment', 'initial-assessment', 45, '1000.00', 'Assessment',
     'Full physical assessment and a personalised treatment plan.'),
    ('Sports Injury Rehab Session', 'sports-injury-rehab-session', 30, '800.00', 'Rehabilitation',
     'Targeted rehabilitation for sprains, strains and sports injuries.'),
    ('Post-Surgical Rehabilitation', 'post-surgical-rehab', 45, '1200.00', 'Rehabilitation',
     'Guided recovery after orthopaedic surgery.'),
    ('Back & Neck Pain Therapy', 'back-neck-pain-therapy', 30, '700.00', 'Pain Management',
     'Manual therapy and exercise for back and neck pain.'),
]

DOCTORS = [
    dict(email='arjun.mehta@physioconnect.demo', first='Arjun', last='Mehta', slug='dr-arjun-mehta',
         spec='Sports Physiotherapy', years=12, fee='800.00',
         qualifications='BPT, MPT (Sports)',
         bio='Helps athletes and active people return to the activities they love after injury.',
         services=['initial-assessment', 'sports-injury-rehab-session', 'post-surgical-rehab']),
    dict(email='neha.kapoor@physioconnect.demo', first='Neha', last='Kapoor', slug='dr-neha-kapoor',
         spec='Orthopaedic Physiotherapy', years=9, fee='700.00',
         qualifications='BPT, MPT (Orthopaedics)',
         bio='Specialises in back, neck and joint pain, with a focus on lasting recovery.',
         services=['initial-assessment', 'back-neck-pain-therapy']),
]


class Command(BaseCommand):
    help = 'Create demo roles, services, doctors, a receptionist and a patient.'

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {n: Role.objects.get_or_create(name=n)[0] for n in ('patient', 'doctor', 'receptionist', 'admin')}

        clinic = ClinicSettings.objects.first() or ClinicSettings()
        clinic.clinic_name = 'PhysioConnect Clinic'
        clinic.cancellation_window_hours = 4
        # Set to your real GST rate. Healthcare services by clinics are often exempt - ask your accountant.
        clinic.default_gst_rate = 0
        clinic.save()

        services = {}
        for name, slug, minutes, price, cat, desc in SERVICES:
            category, _ = ServiceCategory.objects.get_or_create(slug=cat.lower().replace(' ', '-'), defaults={'name': cat})
            services[slug], _ = Service.objects.update_or_create(
                slug=slug, defaults=dict(name=name, duration_minutes=minutes, default_price=price,
                                         description=desc, category=category, is_active=True))

        for d in DOCTORS:
            user, created = User.objects.get_or_create(username=d['email'], defaults=dict(
                email=d['email'], first_name=d['first'], last_name=d['last'], role=roles['doctor']))
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            spec, _ = Specialization.objects.get_or_create(
                slug=d['spec'].lower().replace(' ', '-'), defaults={'name': d['spec']})
            doctor, _ = Doctor.objects.get_or_create(user=user, defaults=dict(
                first_name=d['first'], last_name=d['last'], slug=d['slug'], years_experience=d['years'],
                consultation_fee_default=d['fee'], qualifications=d['qualifications'], bio=d['bio']))
            doctor.specializations.add(spec)
            for slug in d['services']:
                DoctorService.objects.get_or_create(doctor=doctor, service=services[slug])
            if not doctor.availability.exists():
                for day in range(0, 5):   # Monday-Friday
                    DoctorAvailability.objects.create(doctor=doctor, day_of_week=day,
                                                      start_time=datetime.time(9), end_time=datetime.time(17),
                                                      slot_duration_minutes=30)
                DoctorAvailability.objects.create(doctor=doctor, day_of_week=5, start_time=datetime.time(9),
                                                  end_time=datetime.time(13), slot_duration_minutes=30)

        reception, created = User.objects.get_or_create(username='reception@physioconnect.demo', defaults=dict(
            email='reception@physioconnect.demo', first_name='Front', last_name='Desk', role=roles['receptionist']))
        if created:
            reception.set_password(DEMO_PASSWORD)
            reception.save()

        patient_user, created = User.objects.get_or_create(username='patient@physioconnect.demo', defaults=dict(
            email='patient@physioconnect.demo', first_name='Priya', last_name='Sharma', phone='9876500001',
            role=roles['patient']))
        if created:
            patient_user.set_password(DEMO_PASSWORD)
            patient_user.save()
        Patient.objects.get_or_create(user=patient_user, defaults=dict(
            first_name='Priya', last_name='Sharma', created_by=patient_user))

        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
        self.stdout.write(f'  Doctor        arjun.mehta@physioconnect.demo   / {DEMO_PASSWORD}')
        self.stdout.write(f'  Doctor        neha.kapoor@physioconnect.demo   / {DEMO_PASSWORD}')
        self.stdout.write(f'  Receptionist  reception@physioconnect.demo     / {DEMO_PASSWORD}')
        self.stdout.write(f'  Patient       patient@physioconnect.demo       / {DEMO_PASSWORD}')
        self.stdout.write('  (Demo passwords only - change them before real use.)')
