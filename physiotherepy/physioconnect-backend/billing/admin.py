from django.contrib import admin
from .models import Invoice, InvoiceLineItem, Payment


class LineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'patient', 'total', 'status', 'due_date', 'created_at')
    list_filter = ('status',)
    search_fields = ('invoice_number', 'patient__first_name', 'patient__last_name')
    inlines = [LineItemInline, PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'method', 'status', 'paid_at')
    list_filter = ('method', 'status')
