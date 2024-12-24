from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import MarketUser, PaymentTransaction

class PlatformSubscription(models.Model):
    """Instance of the available subscriptions"""

    class SubscriptionTier(models.TextChoices):
        FREE = "FREE", _("Free")
        PREMIUM = "PREM", _("Premium")
        ENTERPRISE = "ENTE", _("Enterprise")

    title = models.CharField(max_length=255)
    description = models.TextField(max_length=255)
    tier = models.CharField(
        max_length=4,
        choices=SubscriptionTier,
        default=SubscriptionTier.FREE,
        unique_for_date="valid_from",
    )

    valid_from = models.DateField()
    valid_to = models.DateField(default="9999-01-01")

    amount_paid_per_month = models.DecimalField(max_digits=10, decimal_places=2)


class ProjectDeveloperSubscription(models.Model):
    """Instance of the choosen Subscription

    A user can have a specific tier, for a choosen timeframe.

    Timeframes will normally last forever.
    Timeframes are termined by setting valid_to to a date >= today()
    """

    class BillingMode(models.TextChoices):
        MONTHLY = "MON", _("Jährlich")
        YEARLY = "YEA", _("Monatlich")

    by_user = models.ForeignKey(
        to=MarketUser, on_delete=models.SET_NULL,
        unique_for_date="valid_from",
        null=True
    )

    tier = models.ForeignKey(to=PlatformSubscription, on_delete=models.SET_NULL, null=True)

    valid_from = models.DateField()
    valid_to = models.DateField(default="9999-01-01")

    billing_mode = models.CharField(
        max_length=3,
        choices=BillingMode,
        default=BillingMode.MONTHLY,
    )

    payments = models.ForeignKey(PaymentTransaction, on_delete=models.SET_NULL, null=True)

class ProjectDeveloperSubscriptionDiscount(models.Model):
    """For timeframes of discounts for users, their subscription fee will be decreased."""

    discount_for_user = models.ForeignKey(
        MarketUser,
        on_delete=models.SET_NULL, 
        unique_for_date="valid_from",
        null=True
    )

    valid_from = models.DateField()
    valid_to = models.DateField()

    amount_percent = models.PositiveSmallIntegerField()
