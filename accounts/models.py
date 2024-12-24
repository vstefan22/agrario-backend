"""Models for user management in the marketplace application.

Defines custom user model and related entities for the accounts application.
"""

import uuid

from django.utils.crypto import get_random_string
from django.contrib.auth.models import AbstractUser
from django.db import models


class MarketUser(AbstractUser):
    """
    Custom user model for the marketplace application.

    Attributes:
        identifier: Unique identifier for the user.
        email: User's unique email address.
        phone_number: Optional phone number of the user.
        address: Optional address of the user.
        is_email_confirmed: Boolean indicating if the user's email is confirmed.
        role: Role of the user (landowner or developer).
        reset_code: Temporary code for password reset.
        reset_code_created_at: Timestamp when the reset code was created.
    """

    ROLE_CHOICES = (
        ("landowner", "Landowner"),
        ("developer", "Project Developer"),
    )
    identifier = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    is_email_confirmed = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="landowner")
    reset_code = models.CharField(max_length=6, null=True, blank=True)
    reset_code_created_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def id(self):
        """
        Alias 'identifier' as 'id' for compatibility.

        Returns:
            UUID: The identifier of the user.
        """
        return self.identifier


class Landowner(MarketUser):
    """
    Model for Landowners, inheriting from MarketUser.

    Attributes:
        position: Optional position or title of the landowner.
    """

    position = models.CharField(max_length=100, null=True, blank=True)


class ProjectDeveloper(MarketUser):
    """
    Model for Project Developers, inheriting from MarketUser.

    Attributes:
        company_name: Optional name of the developer's company.
        company_website: Optional website URL of the company.
    """

    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_website = models.URLField(null=True, blank=True)


class InviteLink(models.Model):
    """
    Model for managing invitation links.

    Attributes:
        uri_hash: Unique hash for the invitation link.
        created_by: User who created the invitation link.
        successful_referrals: Number of successful referrals using the link.
        is_active: Boolean indicating if the link is active.
        created_at: Timestamp when the link was created.
        updated_at: Timestamp when the link was last updated.
    """

    def generate_unique_uri_hash():
        return get_random_string(16)

    uri_hash = models.CharField(
        max_length=16, unique=True, default=generate_unique_uri_hash
    )

    created_by = models.ForeignKey(
        MarketUser, on_delete=models.CASCADE, related_name="invites"
    )
    successful_referrals = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invite by {self.created_by.username} - Active: {self.is_active}"


class PaymentTransaction(models.Model):
    """
    Model to track payment transactions from Stripe.

    Attributes:
        transaction_id: Unique identifier for the transaction.
        status: Status of the transaction (e.g., completed, failed).
        amount: Amount of the transaction.
        email: Email associated with the transaction.
        created_at: Timestamp when the transaction was created.
    """

    transaction_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=50, choices=[("completed", "Completed"), ("failed", "Failed")]
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.status}"


