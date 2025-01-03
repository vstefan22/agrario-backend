"""Models for user management in the marketplace application.

Defines custom user model and related entities for the accounts application.
"""

import uuid

from django.core.validators import MinLengthValidator
from django.contrib.auth.models import AbstractUser
from phonenumber_field.modelfields import PhoneNumberField
from django.db import models
# from django.contrib.gis.db import models as models2
from django.contrib.auth.models import BaseUserManager

class MarketUserManager(BaseUserManager):
    """
    Custom manager for MarketUser without a username field.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)

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
    username = None
    identifier = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(
        region="DE", max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_website = models.URLField(null=True, blank=True)
    profile_picture = models.FileField(upload_to="profile_pictures/", blank=True)
    city = models.CharField(max_length=50, null=True)
    street_housenumber = models.CharField(max_length=50, null=True)
    zipcode = models.CharField(max_length=5)
    is_email_confirmed = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="landowner")
    reset_code = models.CharField(max_length=6, null=True, blank=True)
    reset_code_created_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['first_name', 'last_name', 'company_name', 'address', 'zipcode', 'city', 'phone_number']
    
    objects = MarketUserManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    @property
    def id(self):
        """
        Alias 'identifier' as 'id' for compatibility.

        Returns:
            UUID: The identifier of the user.
        """
        return self.identifier

    def delete(self, *args, **kwargs):
        if self.file:
            self.file.delete()
        super().delete(*args, **kwargs)

class Landowner(MarketUser):
    """
    Model for Landowners, inheriting from MarketUser.

    Attributes:
        position: Optional position or title of the landowner.
    """

    position = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Landowner"
        verbose_name_plural = "Landowners"


class ProjectDeveloper(MarketUser):
    """
    Model for Project Developers, inheriting from MarketUser.

    Attributes:
        company_name: Optional name of the developer's company.
        company_website: Optional website URL of the company.
    """

    interest = models.ForeignKey(
        to="ProjectDeveloperInterest", on_delete=models.CASCADE
    )

    states_active = models.ManyToManyField(to="Region")

    class Meta:
        verbose_name = "Project Developer"
        verbose_name_plural = "Project Developers"
        
class Region(models.Model):

    name = models.CharField(max_length=64)

    # example 'DE-BW' or see https://en.wikipedia.org/wiki/ISO_3166
    iso3166 = models.CharField(
        max_length=5, validators=[MinLengthValidator(5)], null=True, blank=False
    )

    # geom = models2.MultiPolygonField()

class ProjectDeveloperInterest(models.Model):
    """Interest of the project developer"""

    wind = models.BooleanField()

    ground_mounted_solar = models.BooleanField()

    battery = models.BooleanField()

    heat = models.BooleanField()

    hydrogen = models.BooleanField()

    electromobility = models.BooleanField()

    ecological_upgrading = models.BooleanField()

    other = models.CharField(max_length=50)