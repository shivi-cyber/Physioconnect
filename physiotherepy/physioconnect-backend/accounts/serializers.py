from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from core.permissions import get_role
from patients.models import Patient

from .models import Role

User = get_user_model()


def clean_phone(value):
    value = (value or '').strip().replace(' ', '')
    return value or None


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()
    doctor_id = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'phone', 'first_name', 'last_name', 'full_name', 'role', 'patient_id', 'doctor_id')

    def get_role(self, user):
        return get_role(user)

    def get_full_name(self, user):
        return f'{user.first_name} {user.last_name}'.strip() or user.email

    def get_patient_id(self, user):
        profile = getattr(user, 'patient_profile', None)
        return str(profile.id) if profile else None

    def get_doctor_id(self, user):
        profile = getattr(user, 'doctor_profile', None)
        return str(profile.id) if profile else None


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists() or User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_phone(self, value):
        phone = clean_phone(value)
        if phone and User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError('An account with this phone number already exists.')
        return phone

    def validate(self, attrs):
        validate_password(attrs['password'], User(email=attrs['email'], first_name=attrs['first_name']))
        return attrs

    @transaction.atomic
    def create(self, data):
        role, _ = Role.objects.get_or_create(name='patient')
        user = User.objects.create_user(
            username=data['email'], email=data['email'], password=data['password'],
            first_name=data['first_name'], last_name=data['last_name'],
            phone=data.get('phone'), role=role,
        )
        Patient.objects.create(user=user, first_name=data['first_name'], last_name=data['last_name'], created_by=user)
        return user


class LoginSerializer(serializers.Serializer):
    # Accepts email OR phone number
    identifier = serializers.CharField(required=False)
    email = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = (attrs.get('identifier') or attrs.get('email') or '').strip()
        if not identifier:
            raise serializers.ValidationError({'email': 'Enter your email or phone number.'})
        attrs['identifier'] = identifier
        return attrs
