"""
Serializers for the Offers application.

Defines serializers for Landuse, Parcel, AreaOffer, and related models.
"""

from rest_framework import serializers
from .models import (
    Landuse,
    Parcel,
    AreaOffer,
    AreaOfferDocuments,
    AreaOfferConfirmation,
    AreaOfferAdministration,
    Report
)


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


class AuctionPlacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = AreaOffer
        fields = ['id', 'parcel', 'price', 'bidding_conditions', 'documents', 'is_active']
        read_only_fields = ['id', 'is_active', 'created_at']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be a positive value.")
        return value
    
    def validate_parcel(self, value):
        if value.owner != self.context['request'].user:
            raise serializers.ValidationError("You can only create offers for your own parcels.")
        return value
    
class ReportSerializer(serializers.ModelSerializer):
    """
    Serializer for the Report model.
    """
    class Meta:
        model = Report
        fields = '__all__'