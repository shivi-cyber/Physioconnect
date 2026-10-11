from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Role, Permission


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('username', 'email', 'phone', 'role', 'status', 'is_active')
    list_filter = ('role', 'status', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('PhysioConnect', {'fields': ('phone', 'role', 'status', 'email_verified_at', 'phone_verified_at')}),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    filter_horizontal = ('permissions',)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('key', 'description')
