"""
Models for user management in the marketplace application.
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

# Base User Model
class MarketUser(AbstractUser):
    """
    Custom user model for the marketplace application.
    """
    ROLE_CHOICES = (
        ('landowner', 'Landowner'),
        ('developer', 'Project Developer'),
    )
    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    is_email_confirmed = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='landowner')
    reset_code = models.CharField(max_length=6, null=True, blank=True)
    reset_code_created_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def id(self):
        """
        Alias 'identifier' as 'id' for compatibility.
        """
        return self.identifier


class Landowner(MarketUser):
    """
    Model for Landowners, inheriting from MarketUser.
    """
    position = models.CharField(max_length=100, null=True, blank=True)


class ProjectDeveloper(MarketUser):
    """
    Model for Project Developers, inheriting from MarketUser.
    """
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_website = models.URLField(null=True, blank=True)


class InviteLink(models.Model):
    """
    Model for managing invitation links.
    """
    uri_hash = models.CharField(max_length=16, unique=True, default=uuid.uuid4().hex[:16])
    created_by = models.ForeignKey(
        MarketUser,
        on_delete=models.CASCADE,
        related_name='invites'
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
    """
    transaction_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=50, 
        choices=[('completed', 'Completed'), ('failed', 'Failed')]
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.status}"