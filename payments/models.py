from django.db import models
from django.conf import settings
import uuid
from django.utils import timezone

class PaymentTransaction(models.Model):
    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    stripe_payment_intent = models.CharField(max_length=255, unique=True)
    payment_method = models.CharField(max_length=50, choices=[("card", "Credit Card"), ("sofort", "Sofort"), ("paypal", "PayPal")])
    status = models.CharField(max_length=50, choices=[("success", "Success"), ("failed", "Failed"), ("pending", "Pending")], default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transaction {self.identifier} - {self.status}"
    
class DiscountCode(models.Model):
    """
    Represents a discount code for Analyse Plus purchases.
    """
    code = models.CharField(max_length=20, unique=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)  # e.g., 20 for 20%
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()

    def is_valid(self):
        return self.valid_from <= timezone.now() <= self.valid_to
    