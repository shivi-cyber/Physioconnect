from django.contrib import admin
from .models import NotificationTemplate, Notification, NotificationPreference


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('category', 'channel', 'is_active')
    list_filter = ('category', 'channel', 'is_active')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'channel', 'status', 'created_at')
    list_filter = ('category', 'channel', 'status')
