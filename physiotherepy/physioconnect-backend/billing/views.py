from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit
from core.exceptions import business_rule
from core.permissions import ADMIN, PATIENT, RECEPTIONIST, IsFrontDesk, get_role

from .models import Invoice, Payment
from .serializers import MANUAL_METHODS, InvoiceSerializer, ManualPaymentSerializer, amount_paid


def visible_invoices(user):
    qs = Invoice.objects.select_related('patient', 'appointment').prefetch_related(
        'line_items', 'payments__collected_by')
    role = get_role(user)
    if role in (ADMIN, RECEPTIONIST):
        return qs
    if role == PATIENT:
        return qs.filter(patient__user=user)
    return qs.none()  # doctors do not see billing


class InvoiceListView(ListAPIView):
    """GET /api/v1/invoices/?status=pending"""
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        qs = visible_invoices(self.request.user).order_by('-created_at')
        if self.request.query_params.get('status'):
            qs = qs.filter(status=self.request.query_params['status'])
        return qs


class InvoiceDetailView(RetrieveAPIView):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return visible_invoices(self.request.user)


class ManualPaymentView(APIView):
    """POST /api/v1/invoices/<id>/manual-payment/   {"amount": "800.00", "method": "cash|upi|pos_card|other"}"""
    permission_classes = [IsFrontDesk]

    def post(self, request, pk):
        body = ManualPaymentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        amount = body.validated_data['amount']

        with transaction.atomic():
            invoice = get_object_or_404(Invoice.objects.select_for_update(), pk=pk)
            if invoice.status in ('void', 'refunded'):
                raise business_rule('INVALID_STATE', 'This invoice is closed and cannot take payments.')
            paid = amount_paid(Invoice.objects.prefetch_related('payments').get(pk=pk))
            due = invoice.total - paid
            if due <= Decimal('0'):
                raise business_rule('ALREADY_PAID', 'This invoice is already fully paid.')
            if amount > due:
                raise business_rule('OVERPAYMENT', f'Amount is more than the balance due (Rs {due}).')

            Payment.objects.create(
                invoice=invoice, amount=amount, method=MANUAL_METHODS[body.validated_data['method']],
                gateway_name='', status='success', collected_by=request.user, paid_at=timezone.now(),
            )
            invoice.status = 'paid' if amount == due else 'partially_paid'
            invoice.save(update_fields=['status', 'updated_at'])

        audit(request, 'payment.recorded', 'invoice', invoice.id,
              amount=str(amount), method=body.validated_data['method'])
        fresh = visible_invoices(request.user).get(pk=pk)
        return Response(InvoiceSerializer(fresh).data, status=status.HTTP_201_CREATED)
