from django.urls import path

from core.permissions import ADMIN, DOCTOR, RECEPTIONIST

from . import views

urlpatterns = [
    path('appointments/', views.AppointmentListCreateView.as_view()),
    path('appointments/<uuid:pk>/', views.AppointmentDetailView.as_view()),
    path('appointments/<uuid:pk>/cancel/', views.AppointmentCancelView.as_view()),
    path('appointments/<uuid:pk>/reschedule/', views.AppointmentRescheduleView.as_view()),
    path('appointments/<uuid:pk>/check-in/', views.transition_view('check-in', RECEPTIONIST, ADMIN).as_view()),
    path('appointments/<uuid:pk>/start/', views.transition_view('start', DOCTOR, ADMIN).as_view()),
    path('appointments/<uuid:pk>/complete/', views.transition_view('complete', DOCTOR, ADMIN).as_view()),
    path('appointments/<uuid:pk>/no-show/', views.transition_view('no-show', RECEPTIONIST, DOCTOR, ADMIN).as_view()),
    path('appointments/<uuid:pk>/notes/', views.ConsultationNoteView.as_view()),
]
