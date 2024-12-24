"""Models for the Offers application.

Defines models for Landuse, Parcel, AreaOffer, and related entities.
"""

from django.conf import settings
from django.db import models


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
    Model representing a parcel of land.

    Attributes:
        owner: The user who owns the parcel.
        landuse: The land use category for the parcel.
        area: The size of the parcel in square meters.
        coordinates: Geo-coordinates or additional spatial data.
        status: The current status of the parcel (e.g., draft, active).
        created_at: The timestamp when the parcel was created.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parcels"
    )
    landuse = models.CharField(max_length=100, blank=True, null=True)
    area = models.FloatField()  # Area in square meters
    coordinates = models.JSONField()  # Additional geo-coordinates if needed
    status = models.CharField(
        max_length=20,
        choices=[("draft", "Draft"), ("active", "Active")],
        default="draft",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Parcel owned by {self.owner} ({self.area} sqm)"


class AreaOffer(models.Model):
    """
    Model representing an offer for a specific area.

    Attributes:
        parcel: The parcel associated with the offer.
        price: The proposed price for the offer.
        bidding_conditions: Optional conditions for bidding stored as JSON.
        documents: Related documents for the offer.
        is_active: Whether the offer is currently active.
        created_at: The timestamp when the offer was created.
    """

    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="offers")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    bidding_conditions = models.JSONField(null=True, blank=True)
    documents = models.ManyToManyField(
        "AreaOfferDocuments", related_name="linked_offers", blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Offer for {self.parcel} at {self.price} USD"


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


class Report(models.Model):
    """
    Model to store calculated data for a selected parcel or map area.

    Attributes:
        parcel: The parcel associated with the report.
        calculation_result: The result of calculations stored as JSON.
        created_at: The timestamp when the report was created.
    """

    parcel = models.ForeignKey(
        Parcel, on_delete=models.CASCADE, related_name="reports", null=True, blank=True
    )
    calculation_result = models.JSONField()  # Store calculation output as JSON
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"Report for Parcel ID {self.parcel.id if self.parcel else 'Unknown'}"
            f"created at {self.created_at}"
            )
