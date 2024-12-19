from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

# Base User Model
class MarketUser(AbstractUser):
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

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def id(self):
        """Alias 'identifier' as 'id' for compatibility."""
        return self.identifier


# Landowner Model (inherits from MarketUser)
class Landowner(MarketUser):
    position = models.CharField(max_length=100, null=True, blank=True)


# ProjectDeveloper Model (inherits from MarketUser)
class ProjectDeveloper(MarketUser):
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_website = models.URLField(null=True, blank=True)


class InviteLink(models.Model):
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
