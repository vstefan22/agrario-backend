from django.contrib import admin
from .models import PaymentTransaction

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'user', 'amount', 'status', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('identifier', 'user__email')
