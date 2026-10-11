from django.contrib import admin
from .models import (
    Doctor, Specialization, DoctorSpecialization,
    DoctorAvailability, DoctorTimeOff, DoctorService,
)


class AvailabilityInline(admin.TabularInline):
    model = DoctorAvailability
    extra = 1


class DoctorServiceInline(admin.TabularInline):
    model = DoctorService
    extra = 1


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'employment_status', 'years_experience', 'consultation_fee_default')
    search_fields = ('first_name', 'last_name')
    list_filter = ('employment_status',)
    prepopulated_fields = {'slug': ('first_name', 'last_name')}
    inlines = [AvailabilityInline, DoctorServiceInline]


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(DoctorTimeOff)
class DoctorTimeOffAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'start_datetime', 'end_datetime', 'reason')
