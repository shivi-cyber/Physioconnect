from django.urls import path

from . import views

urlpatterns = [
    path('doctors/', views.DoctorListView.as_view()),
    path('doctors/<str:ident>/', views.DoctorDetailView.as_view()),
    path('doctors/<str:ident>/available-slots/', views.AvailableSlotsView.as_view()),
]
