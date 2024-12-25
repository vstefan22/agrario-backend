"""Serializers for the Offers application.

Defines serializers for Landuse, Parcel, AreaOffer, and related models.
"""

from rest_framework import serializers

from .models import (
    AreaOffer,
    AreaOfferAdministration,
    AreaOfferConfirmation,
    AreaOfferDocuments,
    Landuse,
    Parcel,
    Report,
)


class LanduseSerializer(serializers.ModelSerializer):
    """
    Serializer for the Landuse model.
    """

    class Meta:
        model = Landuse
        fields = "__all__"


class ParcelSerializer(serializers.ModelSerializer):
    """
    Serializer for the Parcel model.
    """

    class Meta:
        model = Parcel
        fields = [
            "state_name",
            "district_name",
            "municipality_name",
            "cadastral_area",
            "cadastral_sector",
            "plot_number_main",
            "plot_number_secondary",
            "land_use",
            "area_square_meters",
            "created_by",
        ]
        read_only_fields = ["created_by"]


class AreaOfferSerializer(serializers.ModelSerializer):
    """
    Serializer for the AreaOffer model.
    """

    class Meta:
        model = AreaOffer
        fields = "__all__"


class AreaOfferDocumentsSerializer(serializers.ModelSerializer):
    """
    Serializer for the AreaOfferDocuments model.
    """

    class Meta:
        model = AreaOfferDocuments
        fields = "__all__"


class AreaOfferConfirmationSerializer(serializers.ModelSerializer):
    """
    Serializer for the AreaOfferConfirmation model.
    """

    class Meta:
        model = AreaOfferConfirmation
        fields = "__all__"


class AreaOfferAdministrationSerializer(serializers.ModelSerializer):
    """
    Serializer for the AreaOfferAdministration model.
    """

    class Meta:
        model = AreaOfferAdministration
        fields = "__all__"


class AuctionPlacementSerializer(serializers.ModelSerializer):
    """
    Serializer for placing an auction with validation for price and parcel ownership.
    """

    class Meta:
        model = AreaOffer
        fields = [
            "id",
            "parcel",
            "price",
            "bidding_conditions",
            "documents",
            "is_active",
        ]
        read_only_fields = ["id", "is_active", "created_at"]

    def validate_price(self, value):
        """
        Ensure that the price is a positive value.
        """
        if value <= 0:
            raise serializers.ValidationError({"error": "Price must be a positive value."})
        return value

    def validate_parcel(self, value):
        """
        Ensure that the parcel belongs to the current user.
        """
        if value.owner != self.context["request"].user:
            raise serializers.ValidationError(
                {"error": "You can only create offers for parcels you own."}
            )
        return value


class ReportSerializer(serializers.ModelSerializer):
    """
    Serializer for the Report model.
    """

    class Meta:
        model = Report
        fields = "__all__"
