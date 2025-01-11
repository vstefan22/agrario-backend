"""Serializers for the Offers application.

Defines serializers for Landuse, Parcel, AreaOffer, and related models.
"""

from rest_framework import serializers
from django.contrib.gis.geos import Polygon, MultiPolygon
from django.core.exceptions import ValidationError
from django.contrib.gis.geos.error import GEOSException

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
from django.contrib.gis.gdal import SpatialReference, CoordTransform
from rest_framework_gis.serializers import GeoFeatureModelSerializer

logging.basicConfig(
    # Adjust level as needed (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    level=logging.DEBUG,
    # Format for log messages
    format='%(asctime)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


class ParcelGeoSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Parcel
        fields = ('id', 'alkis_feature_id', 'state_name', 'district_name',
                  'municipality_name', 'cadastral_area', 'area_square_meters', 'cadastral_parcel', 'zipcode', 'communal_district')
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
            "cadastral_parcel",
            "plot_number_main",
            "plot_number_secondary",
            "land_use",
            "area_square_meters",
            "created_by",
            "polygon",
        ]
        read_only_fields = ["created_by", "area_square_meters"]

    def validate_polygon(self, value):
        """
        Custom validation for the polygon field.
        Ensures it is a valid list of lat/lng points and converts to MultiPolygon.
        """
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Polygon must be a list of coordinates.")

        if len(value) < 3:
            raise serializers.ValidationError(
                "Polygon must have at least 3 points.")

        try:
            # Convert lat/lng pairs to (lng, lat) tuples
            coords = [(point["lng"], point["lat"]) for point in value]

            # Ensure the polygon is closed
            if coords[0] != coords[-1]:
                coords.append(coords[0])

            # Create a GEOS Polygon
            polygon = Polygon(coords, srid=4326)

            # Wrap in a MultiPolygon
            multipolygon = MultiPolygon(polygon, srid=4326)

            return multipolygon

        except (KeyError, TypeError, GEOSException) as e:
            logger.error(f"Error validating polygon: {e}")
            raise serializers.ValidationError("Invalid polygon data provided.")

    def create(self, validated_data):
        """
        Create a Parcel instance with validated polygon data.
        """
        logger.info(f"Creating Parcel with data: {validated_data}")
        return super().create(validated_data)

    def validate_area(self, polygon):
        """
        Validate the calculated area to ensure it is within reasonable limits.
        """
        if polygon.area > 10_000_000:  # Example: 10 million m² or 10 km²
            raise serializers.ValidationError(
                "The area of the polygon is too large.")
        return polygon


class AreaOfferDocumentsSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = AreaOfferDocuments
        fields = ["id", "offer", "uploaded_at", "document_url"]
        read_only_fields = ["uploaded_at"]

    def get_document_url(self, obj):
        request = self.context.get('request')
        if obj.document and hasattr(obj.document, 'url'):
            return request.build_absolute_uri(obj.document.url)
        return None


class AreaOfferSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True)
    utilization_display = serializers.CharField(
        source="get_utilization_display", read_only=True)
    preferred_regionality_display = serializers.CharField(
        source="get_preferred_regionality_display", read_only=True)
    shareholder_model_display = serializers.CharField(
        source="get_shareholder_model_display", read_only=True)

    documented_offers = AreaOfferDocumentsSerializer(many=True, read_only=True)

    class Meta:
        model = AreaOffer
        fields = [
            "identifier",
            "offer_number",
            "status",
            "status_display",
            "hide_from_search",
            "available_from",
            "utilization",
            "utilization_display",
            "criteria",
            "preferred_regionality",
            "preferred_regionality_display",
            "shareholder_model",
            "shareholder_model_display",
            "important_remarks",
            "documented_offers"
        ]
        extra_kwargs = {"created_by": {"read_only": True}}

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        return AreaOffer.objects.create(created_by=user, **validated_data)

    def validate_criteria(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Criteria must be a dictionary.")
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
