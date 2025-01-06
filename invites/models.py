from django.db import models
from accounts.models import MarketUser
import uuid

class PromoCode(models.Model):
    """
    Promotional redeem code for discounts on parcel analysis or developer subscriptions.
    """
    created_by = models.ForeignKey(MarketUser, on_delete=models.SET_NULL, null=True, related_name="created_promocodes")
    assigned_to = models.ForeignKey(MarketUser, on_delete=models.SET_NULL, null=True, related_name="assigned_promocodes")
    redeemed_by = models.ForeignKey(MarketUser, on_delete=models.SET_NULL, null=True, related_name="redeemed_promocodes")

    code = models.CharField(max_length=16, unique=True)
    amount_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PromoCode {self.code} ({'Active' if self.is_active else 'Inactive'})"


class InviteLink(models.Model):
    """
    Model for managing user invitation links.
    """
    uri_hash = models.CharField(max_length=16, unique=True, default=uuid.uuid4().hex[:16])
    created_by = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name="invites")
    is_active = models.BooleanField(default=True)
    successful_referrals = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invite by {self.created_by.email} ({'Active' if self.is_active else 'Inactive'})"
