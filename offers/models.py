"""
Models for the Offers application.

Defines models for Landuse, Parcel, AreaOffer, and related entities.
"""

from django.db import models
from django.conf import settings


class Landuse(models.Model):
    """
    Model representing a land use category.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Parcel(models.Model):
    """
    Model representing a parcel of land.
    """
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parcels")
    landuse = models.ForeignKey(Landuse, on_delete=models.SET_NULL, null=True, blank=True)
    area = models.FloatField()  # Area in square meters
    coordinates = models.JSONField()  # Store geographical data as GeoJSON or similar format

    def __str__(self):
        return f"Parcel owned by {self.owner} ({self.area} sqm)"


class AreaOffer(models.Model):
    """
    Model representing an offer for a specific area.
    """
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="offers")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Offer for {self.parcel} at {self.price} USD"


class AreaOfferDocuments(models.Model):
    """
    Model representing documents associated with an area offer.
    """
    offer = models.ForeignKey(AreaOffer, on_delete=models.CASCADE, related_name="documents")
    document = models.FileField(upload_to="area_offer_documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class AreaOfferConfirmation(models.Model):
    """
    Model representing the confirmation of an area offer.
    """
    offer = models.OneToOneField(AreaOffer, on_delete=models.CASCADE, related_name="confirmation")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    confirmed_at = models.DateTimeField(auto_now_add=True)


class AreaOfferAdministration(models.Model):
    """
    Model representing administrative notes and data for an area offer.
    """
    offer = models.ForeignKey(AreaOffer, on_delete=models.CASCADE, related_name="administration")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
