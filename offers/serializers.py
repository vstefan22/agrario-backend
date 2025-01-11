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
)
from reports.models import Report
import logging
from django.contrib.gis.geos import GEOSGeometry
from rest_framework_gis.serializers import GeoFeatureModelSerializer

logger = logging.getLogger(__name__)


class ParcelGeoSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Parcel
        fields = ('id', 'alkis_feature_id', 'state_name', 'district_name',
                  'municipality_name', 'cadastral_area', 'cadastral_parcel', 'zipcode')
        geo_field = 'polygon'


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
            "id",
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
            "polygon",  # Correct field name
        ]
        read_only_fields = ["created_by", "area_square_meters"]

    def create(self, validated_data):
        """
        Override create method to handle polygon conversion and area calculation.
        """
        polygon_data = validated_data.pop("polygon", None)
        if polygon_data:
            # Ensure polygon data is in GeoJSON format
            polygon_geojson = {
                "type": polygon_data.get("type"),
                "coordinates": polygon_data.get("coordinates")
            }
            validated_data["polygon"] = GEOSGeometry(
                str(polygon_geojson))  # Convert GeoJSON to GEOSGeometry
            # Dynamically calculate area
            validated_data["area_square_meters"] = validated_data["polygon"].area

        return super().create(validated_data)


class AreaOfferDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AreaOfferDocuments
        fields = ["id", "offer", "uploaded_at"]
        read_only_fields = ["uploaded_at"]


class AreaOfferSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True)
    utilization_display = serializers.CharField(
        source="get_utilization_display", read_only=True)
    documented_offers = AreaOfferDocumentsSerializer(many=True, read_only=True)

    class Meta:
        model = AreaOffer
        fields = [
            "identifier",
            "offer_number",
            "title",
            "description",
            "status",
            "status_display",
            "hide_from_search",
            "created_by",
            "available_from",
            "utilization",
            "utilization_display",
            "criteria",
            'documented_offers'
        ]

    def validate_offer_number(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Offer number must be a positive integer.")
        return value

    def get_status(self, obj):
        return "Marketing Active" if obj.is_active else "Marketing in Preparation"

    def validate_criteria_text_fields(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Criteria must be a dictionary.")
        return value

    def validate_dropdown_selections(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Dropdown selections must be a dictionary.")
        return value


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
    class Meta:
        model = AreaOffer
        fields = [
            "id",
            "parcel",
            "price",
            "bidding_conditions",
            "documents",
            "is_active",
            "additional_criteria",  # Include dynamic criteria
        ]
        read_only_fields = ["id", "is_active", "created_at"]

    def validate_additional_criteria(self, value):
        # Add custom validation for additional criteria
        required_keys = ["availability_date",
                         "participation_form"]  # Example required keys
        for key in required_keys:
            if key not in value:
                raise serializers.ValidationError(
                    f"Missing required criteria: {key}")
        return value

    def validate_price(self, value):
        """
        Ensure that the price is a positive value.
        """
        if value <= 0:
            raise serializers.ValidationError(
                {"error": "Price must be a positive value."})
        return value

    def validate_parcel(self, value):
        request_user = self.context["request"].user
        if value.created_by != request_user:
            logger.warning(
                "Parcel validation failed: User %s does not own Parcel %s", request_user.id, value.id)
            raise serializers.ValidationError(
                "You can only create offers for parcels you own.")
        return value

    def validate_documents(self, value):
        """
        Ensure that the documents belong to the current user.
        """
        request_user = self.context["request"].user
        for document in value:
            if document.created_by != request_user:
                raise serializers.ValidationError(
                    {"error": "You can only attach documents that you own."}
                )
        return value
