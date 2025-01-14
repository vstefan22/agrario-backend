from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Report
from .serializers import ReportSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from django.contrib.gis.geos import MultiPolygon
from rest_framework.permissions import BasePermission
from rest_framework.views import APIView
from accounts.firebase_auth import verify_firebase_token
from django.http import HttpResponseNotFound, FileResponse
from django.shortcuts import get_object_or_404
import os
from django.conf import settings
import logging
from offers.models import Parcel

logger = logging.getLogger(__name__)


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
    filterset_fields = ["area_m2", "usable_area_solar_m2", "visible_for"]

    def retrieve(self, request, pk=None):
        """
        Retrieve a specific report using UUID.
        """
        report = get_object_or_404(Report, identifier=pk)
        has_analyse_plus = report.purchase_type == "analyse_plus" and report.visible_for == "USER"

        serializer = self.get_serializer(report, context={"analyse_plus": has_analyse_plus})
        data = serializer.data

        data["actions"] = {
            "buy_analyse_plus": not has_analyse_plus,
            "download_report": has_analyse_plus,
        }

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def create_report(self, request):
        """
        Create a report and associate it with parcels.
        """
        try:
            # Extract data from request
            parcel_ids = request.data.get("parcel_ids", [])
            solar_irradiance = float(request.data.get("solar_irradiance", 4.5))
            wind_speed = float(request.data.get("wind_speed", 7.0))
            grid_distance = float(request.data.get("grid_distance", 1000))

            # Validate parcels
            parcels = Parcel.objects.filter(id__in=parcel_ids)
            if not parcels.exists():
                return Response({"error": "No valid parcels found."}, status=status.HTTP_400_BAD_REQUEST)

            # Process the polygon from parcels
            polygon = parcels.first().polygon
            if not polygon:
                return Response({"error": "Polygon data is missing for the selected parcels."}, status=status.HTTP_400_BAD_REQUEST)

            mpoly = MultiPolygon(polygon) if polygon.geom_type == "Polygon" else polygon

            # Calculate metrics
            metrics = Report.calculate_energy_metrics(
                mpoly=mpoly,
                average_solar_irradiance=solar_irradiance,
                average_wind_speed=wind_speed,
                grid_distance=grid_distance,
            )

            # Assign usable_area_m2 as the sum of usable solar and wind areas
            usable_area_m2 = metrics["usable_area_solar_m2"] + metrics["usable_area_wind_m2"]

            # Set default values for missing fields
            default_distance = 1000  # Example default value for distances
            report = Report.objects.create(
                mpoly=mpoly,
                area_m2=metrics["total_area_m2"],
                usable_area_m2=usable_area_m2,
                usable_area_solar_m2=metrics["usable_area_solar_m2"],
                usable_area_wind_m2=metrics["usable_area_wind_m2"],
                usable_area_battery_m2=int(metrics.get("battery_suitability_score", 0) * 100),
                energy_distance_midhigh_m=default_distance,
                energy_distance_highhigh_m=default_distance,
                energy_distance_tower_highest_m=default_distance,  # Provide default value
                energy_distance_tower_high_m=default_distance,     # Provide default value
                energy_distance_tower_mid_m=default_distance,      # Provide default value
                distance_motorway_ramp_m=default_distance,
                distance_motorway_m=default_distance,
                distance_trunkprimary_m=default_distance,
                distance_secondary_m=default_distance,
                distance_traintracks_m=default_distance,
                distance_settlement_m=default_distance,
                eeg_area_m2=metrics["usable_area_solar_m2"] * 0.8,  # Example calculation
                baugb_area_m2=metrics["usable_area_wind_m2"] * 0.5,  # Example calculation
                is_area_in_privilege_area=True,  # Default value
                data=metrics,
            )
            report.parcels.set(parcels)

            # Serialize and return the report
            serializer = self.get_serializer(report)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            logger.error(f"ValueError: {str(e)}")
            return Response({"error": f"Invalid input: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error in create_report: {str(e)}")
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=True, methods=["get"], permission_classes=[FirebaseIsAuthenticated])
    def view_report(self, request, pk=None):
        """
        Retrieve report details with conditional access based on purchase type.
        """
        report = get_object_or_404(Report, identifier=pk)

        # Check Analyse Plus purchase
        is_analyse_plus_purchased = report.purchase_type == "analyse_plus" and \
                                    request.user.role == "landowner"

        serializer = ReportSerializer(
            report,
            context={"request": request, "analyse_plus_purchased": is_analyse_plus_purchased},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)




    # @action(detail=True, methods=["get"])
    # def preview(self, request, pk=None):
    #     """
    #     Provide a preview of the report with limited data.
    #     """
    #     report = get_object_or_404(Report, identifier=pk)
    #     serializer = self.get_serializer(report, context={"analyse_plus": False})
    #     return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """
        Allow downloading a sample report file.
        """
        file_path = os.path.join(settings.STATIC_ROOT, "reports/sample_report.zip")
        if not os.path.exists(file_path):
            return HttpResponseNotFound({"error": "File not found."})

        response = FileResponse(open(file_path, "rb"), content_type="application/zip")
        response["Content-Disposition"] = f"attachment; filename=sample_report.zip"
        return response


class DownloadReportView(APIView):
    """
    API view to download a sample report file.
    """
    permission_classes = [FirebaseIsAuthenticated]

    def get(self, request, report_id=None):
        """
        Serve a pre-generated report file.
        """
        # Example file path (replace with your actual static file path or cloud bucket URL)
        file_path = os.path.join(settings.STATIC_ROOT, "reports/sample_report.zip")
        
        # Check if the file exists
        if not os.path.exists(file_path):
            return HttpResponseNotFound({"error": "File not found."})

        # Serve the file
        response = FileResponse(open(file_path, "rb"), content_type="application/zip")
        response["Content-Disposition"] = f"attachment; filename=sample_report.zip"
        return response