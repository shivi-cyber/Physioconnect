"""URL configuration for the physioconnect project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('accounts.urls')),
    path('api/v1/', include('core.urls')),
    path('api/v1/', include('doctors.urls')),
    path('api/v1/', include('patients.urls')),
    path('api/v1/', include('appointments.urls')),
    path('api/v1/', include('billing.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
