from django.urls import path

from . import views

urlpatterns = [
    path('services/', views.ServiceListView.as_view()),
    path('clinic/', views.ClinicInfoView.as_view()),
    path('dashboard/', views.DashboardView.as_view()),
]
