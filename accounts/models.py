"""Models for user management in the marketplace application.

Defines custom user model and related entities for the accounts application.
"""

import uuid, datetime

from django.core.validators import MinLengthValidator, URLValidator, MaxValueValidator, MinValueValidator
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from django.apps import apps
# from django.contrib.gis.db import models as models2
from django.contrib.auth.models import BaseUserManager

def validate_url(value):

    validator = URLValidator()
    
    if value.startswith(('http://', 'https://')):
        try:
            validator(value)
        except ValidationError:
            raise ValidationError("URL is not valid.")
    elif value.startswith('www.'):
        try:
            validator(f"https://{value}")
        except ValidationError:
            raise ValidationError("URL is not valid.")
    else:
        raise ValidationError("URL must start with 'http://', 'https://' or 'www.'.")

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
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_website = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        validators=[validate_url]
    )
    position = models.CharField(max_length=100, null=True, blank=True)
    profile_picture = models.FileField(
        upload_to="profile_pictures/", blank=True)
    city = models.CharField(max_length=50, null=True)
    zipcode = models.CharField(max_length=5)
    is_email_confirmed = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES)
    reset_code = models.CharField(max_length=6, null=True, blank=True)
    reset_code_created_at = models.DateTimeField(null=True, blank=True)
    privacy_accepted = models.BooleanField(default=False)
    terms_accepted = models.BooleanField(default=False)
    privacy_accepted = models.BooleanField(default=False)
    terms_accepted = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'

    objects = MarketUserManager()
    REQUIRED_FIELDS = ['first_name', 'last_name', 'company_name',
                       'address', 'zipcode', 'city', 'phone_number']

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
    class Meta:
        verbose_name = "Landowner"
        verbose_name_plural = "Landowners"

current_year = datetime.datetime.now().year

class ProjectDeveloper(MarketUser):
    """
    Model for Project Developers, inheriting from MarketUser.
    """
    interest = models.ForeignKey(
        to="ProjectDeveloperInterest", on_delete=models.CASCADE
    )
    company_logo = models.FileField(
        upload_to="company_logos/", null=True, blank=True)
    founding_year = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1500),
            MaxValueValidator(datetime.datetime.now().year)
        ],
        blank=True,
        null=True
    )
    mw_capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        blank=True,
        null=True,
    )
    employees = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        blank=True,
        null=True,
    )
    states_active = models.ManyToManyField(to="Region")
    tier = models.ForeignKey(
        "subscriptions.PlatformSubscription",  # Use string reference
        on_delete=models.CASCADE,
        null=True,  # Allow null to avoid immediate integrity errors
        blank=True
    )

    class Meta:
        verbose_name = "Project Developer"
        verbose_name_plural = "Project Developers"

    def save(self, *args, **kwargs):
        """
        Dynamically assign the "Free Plan" if the tier is not already set.
        """
        if not self.tier_id:
            PlatformSubscription = apps.get_model("subscriptions", "PlatformSubscription")
            try:
                self.tier = PlatformSubscription.objects.get(tier="FREE")
            except PlatformSubscription.DoesNotExist:
                raise ValueError("Default subscription plan (Free Plan) does not exist.")
        super().save(*args, **kwargs)

    def upgrade_privileges(self, plan):
        """
        Updates the user's privileges based on the selected subscription plan.
        """
        self.tier = plan
        self.save()

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

    other = models.CharField(max_length=50, blank=True)
