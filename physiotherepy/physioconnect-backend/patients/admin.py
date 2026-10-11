from django.contrib import admin
from .models import Patient, PatientMedicalProfile, Document


class MedicalProfileInline(admin.StackedInline):
    model = PatientMedicalProfile
    can_delete = False


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'user', 'city', 'referral_source', 'created_at')
    search_fields = ('first_name', 'last_name', 'user__phone', 'user__email')
    list_filter = ('referral_source', 'city')
    inlines = [MedicalProfileInline]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('label', 'patient', 'uploaded_by', 'uploaded_at')
