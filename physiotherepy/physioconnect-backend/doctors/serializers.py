from rest_framework import serializers

from .models import Doctor, DoctorAvailability, DoctorService


class DoctorServiceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='service.id')
    name = serializers.CharField(source='service.name')
    description = serializers.CharField(source='service.description')
    duration_minutes = serializers.IntegerField(source='service.duration_minutes')
    price = serializers.DecimalField(source='effective_price', max_digits=8, decimal_places=2)

    class Meta:
        model = DoctorService
        fields = ('id', 'name', 'description', 'duration_minutes', 'price')


class AvailabilitySerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display')

    class Meta:
        model = DoctorAvailability
        fields = ('day_of_week', 'day_name', 'start_time', 'end_time', 'slot_duration_minutes')


class DoctorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    specializations = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = (
            'id', 'slug', 'name', 'first_name', 'last_name', 'specializations',
            'qualifications', 'bio', 'years_experience', 'photo',
            'consultation_fee_default', 'services',
        )

    def get_name(self, doc):
        return f'Dr. {doc.first_name} {doc.last_name}'

    def get_specializations(self, doc):
        return [s.name for s in doc.specializations.all()]

    def get_photo(self, doc):
        if not doc.profile_photo:
            return None
        request = self.context.get('request')
        url = doc.profile_photo.url
        return request.build_absolute_uri(url) if request else url

    def get_services(self, doc):
        links = [ds for ds in doc.doctor_services.all() if ds.service.is_active]
        return DoctorServiceSerializer(links, many=True).data


class DoctorDetailSerializer(DoctorSerializer):
    weekly_availability = serializers.SerializerMethodField()

    class Meta(DoctorSerializer.Meta):
        fields = DoctorSerializer.Meta.fields + ('weekly_availability',)

    def get_weekly_availability(self, doc):
        rules = [r for r in doc.availability.all() if r.is_active]
        rules.sort(key=lambda r: (r.day_of_week, r.start_time))
        return AvailabilitySerializer(rules, many=True).data
