"""
Serializers for the Offers application.

Defines serializers for Landuse, Parcel, AreaOffer, and related models.
"""

from rest_framework import serializers
from .models import Landuse, Parcel, AreaOffer


class LanduseSerializer(serializers.ModelSerializer):
    """
    Serializer for the Landuse model.
    """
    class Meta:
        model = Landuse
        fields = '__all__'


class ParcelSerializer(serializers.ModelSerializer):
    """
    Serializer for the Parcel model.
    """
    class Meta:
        model = Parcel
        fields = '__all__'


class AreaOfferSerializer(serializers.ModelSerializer):
    """
    Serializer for the AreaOffer model.
    """
    class Meta:
        model = AreaOffer
        fields = '__all__'


from rest_framework import serializers
from .models import (
    AreaOfferDocuments,
    AreaOfferConfirmation,
    AreaOfferAdministration
)


class AreaOfferDocumentsSerializer(serializers.ModelSerializer):
    """Serializer for AreaOfferDocuments model."""

    class Meta:
        model = AreaOfferDocuments
        fields = '__all__'


class AreaOfferConfirmationSerializer(serializers.ModelSerializer):
    """Serializer for AreaOfferConfirmation model."""

    class Meta:
        model = AreaOfferConfirmation
        fields = '__all__'


class AreaOfferAdministrationSerializer(serializers.ModelSerializer):
    """Serializer for AreaOfferAdministration model."""

    class Meta:
        model = AreaOfferAdministration
        fields = '__all__'
