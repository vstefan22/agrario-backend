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
    Defines the geometry of areas of land that landowners want to put on the marketplace.

    Attributes:
        state_name: Name of the state where the parcel is located.
        district_name: Name of the district where the parcel is located.
        municipality_name: Name of the municipality.
        cadastral_area: Cadastral area of the parcel.
        cadastral_sector: Cadastral sector of the parcel.
        plot_number_main: Main plot number.
        plot_number_secondary: Secondary plot number.
        land_use: Description of land usage.
        area_square_meters: Area of the parcel in square meters.
        appear_in_offer: Foreign key linking to an AreaOffer.
        created_by: User who created the parcel.
        created_at: Timestamp when the parcel was created.
    """

    state_name = models.CharField(max_length=64)
    district_name = models.CharField(max_length=64)
    municipality_name = models.CharField(max_length=64)
    cadastral_area = models.CharField(max_length=64)
    cadastral_sector = models.CharField(max_length=64)
    plot_number_main = models.CharField(max_length=8, null=True)
    plot_number_secondary = models.CharField(max_length=8)
    land_use = models.CharField(max_length=255)
    area_square_meters = models.DecimalField(max_digits=12, decimal_places=2)

    appear_in_offer = models.ForeignKey(
        "AreaOffer", related_name="parcels", on_delete=models.SET_NULL, null=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_parcels"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Parcel in {self.state_name}, {self.district_name}"


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

    parcel = models.ForeignKey(
        Parcel, on_delete=models.CASCADE, related_name="offers")
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
    calculation_result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        parcel_id = self.parcel.id if self.parcel else "Unknown"
        return f"Report for Parcel ID {parcel_id} created at {self.created_at}"
