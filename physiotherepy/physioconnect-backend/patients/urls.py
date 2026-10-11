from django.urls import path

from . import views

urlpatterns = [
    path('patients/', views.PatientListCreateView.as_view()),
    path('patients/<uuid:pk>/', views.PatientDetailView.as_view()),
    path('patients/<uuid:pk>/history/', views.PatientHistoryView.as_view()),
    path('patients/<uuid:pk>/medical-profile/', views.MedicalProfileView.as_view()),
]
