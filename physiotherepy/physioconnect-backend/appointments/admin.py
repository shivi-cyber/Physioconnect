from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'service', 'scheduled_start', 'status', 'booking_channel')
    list_filter = ('status', 'booking_channel', 'doctor')
    search_fields = ('patient__first_name', 'patient__last_name', 'doctor__first_name', 'doctor__last_name')
    date_hierarchy = 'scheduled_start'
