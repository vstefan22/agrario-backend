from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Report
from .serializers import ReportSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from django.contrib.gis.geos import MultiPolygon
from rest_framework.permissions import BasePermission
from accounts.firebase_auth import verify_firebase_token
from offers.models import Parcel


class FirebaseIsAuthenticated(BasePermission):
    """
    Custom permission class for Firebase authentication.
    """
    def has_permission(self, request, view):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            request.error_message = {"error": "Authentication header or Bearer token is missing."}
            return False

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            request.error_message = {"error": "Invalid or expired Firebase token."}
            return False

        request.user_email = decoded_token.get("email")
        request.user_role = decoded_token.get("role", "user")
        return True

class ReportPagination(PageNumberPagination):
    page_size = 10

class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Report instances.
    """

    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [FirebaseIsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['area_m2', 'usable_area_solar_m2', 'visible_for']
    pagination_class = ReportPagination

    @action(detail=False, methods=["post"])
    def create_report(self, request):
        """
        Create a report with calculated energy suitability metrics and link it to parcels.
        """
        try:
            # Extract input data
            parcel_ids = request.data.get("parcel_ids", [])
            solar_irradiance = float(request.data.get("solar_irradiance", 4.5))  # Default: 4.5
            wind_speed = float(request.data.get("wind_speed", 7.0))  # Default: 7.0
            grid_distance = float(request.data.get("grid_distance", 1000))  # Default: 1000m

            # Validate parcels
            parcels = Parcel.objects.filter(id__in=parcel_ids)
            if not parcels.exists():
                return Response({"error": "No valid parcels found."}, status=status.HTTP_400_BAD_REQUEST)

            # Extract the polygon from the first parcel
            polygon = parcels.first().polygon
            if polygon.geom_type == "Polygon":
                mpoly = MultiPolygon(polygon)  # Convert Polygon to MultiPolygon
            elif polygon.geom_type == "MultiPolygon":
                mpoly = polygon  # Already a MultiPolygon
            else:
                return Response({"error": "Invalid geometry type for parcel polygon."}, status=status.HTTP_400_BAD_REQUEST)

            # Calculate metrics
            metrics = Report.calculate_energy_metrics(
                mpoly=mpoly,
                average_solar_irradiance=solar_irradiance,
                average_wind_speed=wind_speed,
                grid_distance=grid_distance,
            )

            # Populate default or calculated values for all fields
            report = Report.objects.create(
                mpoly=mpoly,
                area_m2=metrics["total_area_m2"],
                usable_area_m2=metrics["usable_area_solar_m2"],
                usable_area_solar_m2=metrics["usable_area_solar_m2"],
                usable_area_wind_m2=metrics["usable_area_wind_m2"],
                usable_area_battery_m2=metrics["battery_suitability_score"],
                energy_distance_midhigh_m=grid_distance,  # Example default value
                energy_distance_highhigh_m=grid_distance,  # Example default value
                energy_distance_tower_highest_m=grid_distance,
                energy_distance_tower_high_m=grid_distance,
                energy_distance_tower_mid_m=grid_distance,
                distance_motorway_ramp_m=1000,  # Example default value
                distance_motorway_m=2000,  # Example default value
                distance_trunkprimary_m=3000,  # Example default value
                distance_secondary_m=1500,  # Example default value
                distance_traintracks_m=2500,  # Example default value
                distance_settlement_m=500,  # Example default value
                eeg_area_m2=metrics["usable_area_solar_m2"] * 0.8,  # Example calculation
                baugb_area_m2=metrics["usable_area_wind_m2"] * 0.5,  # Example calculation
                is_area_in_privilege_area=True,  # Example default value
                data=metrics,
            )

            # Link parcels to the report
            report.parcels.set(parcels)

            # Serialize and return the report
            serializer = ReportSerializer(report)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        
        
    @action(detail=True, methods=["get"])
    def retrieve_report(self, request, pk=None):
        """
        Retrieve details of a specific report.
        """
        try:
            report = self.get_object()
            serializer = self.get_serializer(report)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Report.DoesNotExist:
            return Response({"error": "Report not found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"])
    def list_reports(self, request):
        """
        List all reports in the system.
        """
        reports = self.get_queryset()
        serializer = self.get_serializer(reports, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Report.objects.all()
        elif user.role == "landowner":
            return Report.objects.filter(visible_for__in=["USER", "PUBLIC"])
        return Report.objects.filter(visible_for="PUBLIC")
