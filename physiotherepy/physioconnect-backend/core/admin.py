from django.contrib import admin
from .models import ServiceCategory, Service, ClinicSettings, AuditLog


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'duration_minutes', 'default_price', 'is_active')
    list_filter = ('category', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ClinicSettings)
class ClinicSettingsAdmin(admin.ModelAdmin):
    list_display = ('clinic_name', 'phone', 'email', 'gstin')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('actor', 'action', 'entity_type', 'entity_id', 'created_at')
    list_filter = ('entity_type',)
    search_fields = ('action', 'entity_id')
    readonly_fields = [f.name for f in AuditLog._meta.fields]  # append-only: no editing from admin

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
