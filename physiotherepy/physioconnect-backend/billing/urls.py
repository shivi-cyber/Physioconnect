from django.urls import path

from . import views

urlpatterns = [
    path('invoices/', views.InvoiceListView.as_view()),
    path('invoices/<uuid:pk>/', views.InvoiceDetailView.as_view()),
    path('invoices/<uuid:pk>/manual-payment/', views.ManualPaymentView.as_view()),
]
