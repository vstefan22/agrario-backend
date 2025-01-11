"""Models for the Offers application.

Defines models for Landuse, Parcel, AreaOffer, and related entities.
"""

from django.conf import settings
from django.db import models
from django.db.models import JSONField
from django.contrib.gis.db import models as gis_models
import uuid
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import Landowner, MarketUser
import random


class Landuse(models.Model):
    """
    Model representing a land use category.

    Attributes:
        name: The name of the land use category.
        description: An optional detailed description of the category.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Parcel(models.Model):
    """
    Defines the geometry of areas of land that landowners want to put on the marketplace.

    Attributes:
        state_name: Name of the state where the parcel is located.
        district_name: Name of the district where the parcel is located.
        municipality_name: Name of the municipality.
        cadastral_area: Cadastral area of the parcel.
        cadastral_parcel: Cadastral sector of the parcel.
        plot_number_main: Main plot number.
        plot_number_secondary: Secondary plot number.
        land_use: Description of land usage.
        area_square_meters: Area of the parcel in square meters.
        appear_in_offer: Foreign key linking to an AreaOffer.
        created_by: User who created the parcel.
        created_at: Timestamp when the parcel was created.
    """

    STATUS_CHOICES = [
        ("available", "Available"),
        ("purchased", "Purchased"),
    ]
    alkis_feature_id = models.CharField(max_length=30)
    zipcode = models.CharField(null=True, blank=True, max_length=30)

    state_name = models.CharField(max_length=255)
    district_name = models.CharField(max_length=255)
    municipality_name = models.CharField(max_length=255)
    cadastral_area = models.CharField(max_length=255)

    communal_district = models.CharField(max_length=64)
    cadastral_parcel = models.CharField(max_length=255)

    plot_number_main = models.CharField(max_length=8, null=True)
    plot_number_secondary = models.CharField(max_length=8)
    land_use = models.CharField(null=True, blank=True, max_length=255)
    area_square_meters = models.DecimalField(max_digits=12, decimal_places=2)

    polygon = gis_models.MultiPolygonField(
        null=True, blank=True)  # GeoDjango field for polygons
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="available")

    appear_in_offer = models.ForeignKey(
        "AreaOffer", related_name="parcels", on_delete=models.SET_NULL, null=True
    )
    created_by = models.ForeignKey(

        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="created_parcels"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Parcel in {self.state_name}, {self.district_name}"


class BasketItem(models.Model):
    """
    Represents a parcel in the user's basket.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="basket_items")
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "parcel")


class AreaOffer(models.Model):
    """
    Represents an offer containing multiple parcels and criteria set by the landowner.
    """

    identifier = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)

    offer_number = models.PositiveIntegerField(
        auto_created=True, unique=True, editable=False)
    # title = models.CharField(max_length=255)
    # description = models.TextField()
    # Dynamic key-value pairs
    criteria = models.JSONField(default=dict, blank=True)

    class OfferStatus(models.TextChoices):
        IN_PREPARATION = "V", _("In Vorbereitung")  # after creation
        PREPARED = "P", _("Vorprüfung abgeschlossen")
        ACTIVE = "A", _("Aktiv")
        INACTIVE = "I", _("Inaktiv")

    status = models.CharField(
        max_length=2, choices=OfferStatus.choices, default=OfferStatus.IN_PREPARATION
    )
    hide_from_search = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        MarketUser, on_delete=models.SET_NULL, null=True, related_name="area_offers"
    )
    available_from = models.DateField()

    def save(self, *args, **kwargs):
        if not self.offer_number:
            self.offer_number = self.generate_offer_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_offer_number():
        while True:
            offer_number = random.randint(100000, 999999)
            if not AreaOffer.objects.filter(offer_number=offer_number).exists():
                return offer_number

    class AreaUtilization(models.TextChoices):
        NO_RESTRICTION = "NO", _("No Restriction")
        SALE = "SA", _("Sale")
        LEASE = "LE", _("Lease")

    utilization = models.CharField(
        max_length=2, choices=AreaUtilization.choices, default=AreaUtilization.NO_RESTRICTION
    )

    # excluded_landuse = models.ManyToManyField(Landuse, related_name="offers")

    class DeveloperRegionality(models.TextChoices):
        NO_RESTRICTION = "NO", _("Keine Einschränkung")
        GERMANY = "DE", _("Firmensitz in Deutschland")
        FEDERAL_STATE = "BL", _("Firmensitz im Bundesland des Grundstücks")

    preferred_regionality = models.TextField(
        choices=DeveloperRegionality, default=DeveloperRegionality.NO_RESTRICTION
    )

    class ShareholderModel(models.TextChoices):
        NO_RESTRICTION = "NO", _("Keine Einschränkung")
        SHARES_INCOME = "IN", _("Beteiligungen am Erlös")
        SHARES_COMPANY = "CO", _("Beteiligungen an der Projektgesellschaft")
        BOTH = "BO", _("Beides")

    shareholder_model = models.TextField(
        choices=ShareholderModel, default=ShareholderModel.NO_RESTRICTION
    )

    important_remarks = models.TextField()

    def __str__(self):
        return f"Offer #{self.offer_number}"


class AreaOfferDocuments(models.Model):
    """
    Model representing documents associated with an area offer.

    Attributes:
        offer: The offer to which this document belongs.
        document: The file uploaded for the offer.
        uploaded_at: The timestamp when the document was uploaded.
    """

    offer = models.ForeignKey(
        AreaOffer, on_delete=models.CASCADE, related_name="documented_offers"
    )
    document = models.FileField(upload_to="area_offer_documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class AreaOfferConfirmation(models.Model):
    """
    Model representing the confirmation of an area offer.

    Attributes:
        offer: The offer that is being confirmed.
        confirmed_by: The user who confirmed the offer.
        confirmed_at: The timestamp when the offer was confirmed.
    """

    offer = models.OneToOneField(
        AreaOffer, on_delete=models.CASCADE, related_name="confirmation"
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    confirmed_at = models.DateTimeField(auto_now_add=True)


class AreaOfferAdministration(models.Model):
    """
    Model representing administrative notes and data for an area offer.

    Attributes:
        offer: The offer to which the administrative notes belong.
        notes: The notes or additional information.
        created_at: The timestamp when the notes were added.
    """

    offer = models.ForeignKey(
        AreaOffer, on_delete=models.CASCADE, related_name="administration"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Region(models.Model):

    name = models.CharField(max_length=64)

    # example 'DE-BW' or see https://en.wikipedia.org/wiki/ISO_3166
    iso3166 = models.CharField(
        max_length=5, validators=[MinLengthValidator(5)], null=True, blank=False
    )

    geom = gis_models.MultiPolygonField(null=True, blank=True)
