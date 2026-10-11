from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from accounts.models import Role
from accounts.serializers import clean_phone

from .models import Patient, PatientMedicalProfile

User = get_user_model()

EDITABLE_FIELDS = (
    'first_name', 'last_name', 'dob', 'gender', 'address', 'city', 'state', 'postal_code',
    'emergency_contact_name', 'emergency_contact_phone', 'blood_group',
)


class PatientSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)

    class Meta:
        model = Patient
        fields = ('id', 'first_name', 'last_name', 'email', 'phone', 'dob', 'gender', 'address', 'city',
                  'state', 'postal_code', 'emergency_contact_name', 'emergency_contact_phone',
                  'blood_group', 'referral_source', 'created_at')
        read_only_fields = ('id', 'referral_source', 'created_at')


class PatientUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = EDITABLE_FIELDS


class MedicalProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientMedicalProfile
        fields = ('known_conditions', 'allergies', 'current_medications', 'notes', 'updated_at')
        read_only_fields = ('updated_at',)


class WalkInPatientSerializer(serializers.Serializer):
    """Receptionist registers a patient who walked in or phoned."""
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=15)
    email = serializers.EmailField(required=False, allow_blank=True)
    dob = serializers.DateField(required=False)
    gender = serializers.ChoiceField(choices=['male', 'female', 'other'], required=False)
    referral_source = serializers.ChoiceField(
        choices=['google', 'referral', 'walk_in', 'social', 'other'], required=False, default='walk_in')

    def validate_phone(self, value):
        phone = clean_phone(value)
        if not phone:
            raise serializers.ValidationError('Phone number is required.')
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError('A patient with this phone number already exists.')
        return phone

    def validate_email(self, value):
        value = (value or '').lower().strip()
        if value and (User.objects.filter(email__iexact=value).exists()
                      or User.objects.filter(username__iexact=value).exists()):
            raise serializers.ValidationError('A patient with this email already exists.')
        return value

    @transaction.atomic
    def create(self, data):
        role, _ = Role.objects.get_or_create(name='patient')
        email = data.get('email', '')
        user = User(
            username=email or f"walkin-{data['phone']}", email=email, phone=data['phone'],
            first_name=data['first_name'], last_name=data['last_name'], role=role,
        )
        user.set_unusable_password()  # they can use "forgot password" later to get online access
        user.save()
        return Patient.objects.create(
            user=user, first_name=data['first_name'], last_name=data['last_name'],
            dob=data.get('dob'), gender=data.get('gender', ''),
            referral_source=data['referral_source'], created_by=self.context['request'].user,
        )
