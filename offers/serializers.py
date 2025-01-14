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
    Watchlist,
    BasketItem
)
from reports.models import Report
import logging
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
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
    We'll make `polygon` read-only and define `polygon_coords`
    for the list of { lat, lng } points from the frontend.
    """

    # `polygon` is read-only in API, so DRF won't try to parse it as geometry
    polygon = serializers.SerializerMethodField(read_only=True)
    # id = serializers.UUIDField(source='identifier')

    # We'll expect an array of objects like [{ lat: 51.8, lng: 7.46 }, ... ]
    # on POST/PUT requests
    polygon_coords = serializers.ListField(
        child=serializers.DictField(child=serializers.FloatField()),
        write_only=True,
        required=False,
        help_text="Array of { lat, lng } points describing the polygon ring."
    )

    class Meta:
        model = Parcel
        fields = [
            "id",
            "zipcode",
            "state_name",
            "district_name",
            "municipality_name",
            "cadastral_area",
            "cadastral_parcel",
            "communal_district",
            "plot_number_main",
            "plot_number_secondary",
            "land_use",
            "area_square_meters",
            "status",
            "appear_in_offer",
            "created_by",
            "polygon",            # read-only
            "polygon_coords",     # write-only
            "alkis_feature_id",
            "analyse_plus",
        ]
        read_only_fields = ["created_by", "area_square_meters", "polygon"]

    def get_polygon(self, obj):
        """
        Return a simple representation of the polygon if you want to
        show it in GET responses. For example, GeoJSON or WKT.
        """
        if obj.polygon:
            return obj.polygon.geojson  # or obj.polygon.wkt
        return None

    def create(self, validated_data):
        """
        Build the real 'polygon' from `polygon_coords` if provided.
        """
        polygon_coords = validated_data.pop("polygon_coords", None)

        if polygon_coords and isinstance(polygon_coords, list):
            logger.info(f"Received polygon_coords: {polygon_coords}")

            # Convert that array of { lat, lng } to a GeoJSON "Polygon"
            ring = []
            for point in polygon_coords:
                # Each `point` is a dict: { "lat": ..., "lng": ... }
                lat = point["lat"]
                lng = point["lng"]
                ring.append([lng, lat])  # GeoJSON order: [lng, lat]

            # Close the ring if needed (first == last)
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])

            polygon_geojson = {
                "type": "Polygon",
                "coordinates": [ring],  # single ring
            }
            logger.info(f"Constructed Polygon GeoJSON: {polygon_geojson}")

            try:
                geom = GEOSGeometry(str(polygon_geojson), srid=4326)
                # If you want to calculate area in m², transform to WebMerc (EPSG:3857) or any projected SRID
                if geom.geom_type == "Polygon":
                    geom = MultiPolygon(geom, srid=geom.srid)
                geom_3857 = geom.clone()
                geom_3857.transform(3857)
                area_sqm = geom_3857.area

                validated_data["polygon"] = geom  # store in lat/lng
                validated_data["area_square_meters"] = round(area_sqm, 2)
            except Exception as e:
                logger.error(
                    f"Error creating geometry from polygon_coords: {e}")
                raise serializers.ValidationError({
                    "polygon": ["Invalid polygon coordinates."]
                })

        # If not provided, do nothing; polygon remains None
        return super().create(validated_data)

    def update(self, instance, validated_data):

        request = self.context.get('request')
        user = request.user if request else None

        if instance.created_by is None:
            instance.created_by = user
            instance.save()
        else:
            raise serializers.ValidationError({
                "error": "Parcel already has an assigned user."
            })

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class BasketItemSerializer(serializers.ModelSerializer):
    parcel = ParcelSerializer()

    class Meta:
        model = BasketItem
        fields = ["id", "parcel", "added_at", "user"]

    def to_representation(self, instance):
        from accounts.serializers import LandownerSerializer

        representation = super().to_representation(instance)
        representation['user'] = LandownerSerializer(instance.user).data
        return representation


class ParcelListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing parcels with limited fields.
    """
    class Meta:
        model = Parcel
        fields = ["id", "state_name", "land_use",
                  "area_square_meters", "polygon"]
        read_only_fields = ["id", "area_square_meters"]


class WatchlistSerializer(serializers.ModelSerializer):
    """
    Serializer for user's watchlist.
    """
    parcel_details = ParcelSerializer(source="parcel", read_only=True)

    class Meta:
        model = Watchlist
        fields = ["id", "parcel", "parcel_details", "added_at"]
        read_only_fields = ["added_at"]


class ParcelDetailsSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed parcel view with field blurring based on restrictions.
    """

    blurred_fields = ["plz", "gemeinde", "gemarkung", "flur", "flurstueck"]
    id = serializers.UUIDField(source='identifier')

    def to_representation(self, instance):
        """
        Blur specific fields and restrict data for sensitive sections.
        """
        data = super().to_representation(instance)

        # Blur specific fields in the table
        for field in self.blurred_fields:
            if field in data:
                data[field] = "*****"

        # Blur fields under "Lage und Nutzung" accordion
        # Replace with actual fields
        accordion_fields = ["lage_detail", "nutzung_detail"]
        for field in accordion_fields:
            if field in data:
                data[field] = "*****"

        return data

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
            "polygon",
            "plz",
            "gemeinde",
            "gemarkung",
            "flur",
            "flurstueck",
            "lage_detail",  # Example field under "Lage und Nutzung"
            "nutzung_detail",  # Example field under "Lage und Nutzung"
        ]


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

    parcels = ParcelSerializer(many=True, read_only=True)

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
            "documented_offers",
            "parcels",
        ]
        extra_kwargs = {"created_by": {"read_only": True}}

    def create(self, validated_data):
        """
        Ensure the `created_by` field is set dynamically in the ViewSet, not here.
        """
        return super().create(validated_data)

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
