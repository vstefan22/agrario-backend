from django.db import models
from django.conf import settings
import uuid

class PaymentTransaction(models.Model):
    """
    Model to store payment transactions.
    """
    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    stripe_payment_intent = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=50, choices=[("success", "Success"), ("failed", "Failed"), ("pending", "Pending")], default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transaction {self.identifier} - {self.status}"
