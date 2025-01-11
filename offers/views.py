"""Views for the Offers application.

Provides endpoints for managing land use, parcels, area offers, and associated documents.
"""

from decimal import Decimal
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.db.models.functions import Transform
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView
from rest_framework_gis.pagination import GeoJsonPagination

from accounts.models import MarketUser
from payments.models import PaymentTransaction
from reports.models import Report
from .models import (
    AreaOffer,
    AreaOfferConfirmation,
    AreaOfferDocuments,
    Landuse,
    Parcel,
)
from .serializers import (
    AreaOfferDocumentsSerializer,
    AreaOfferSerializer,
    AuctionPlacementSerializer,
    LanduseSerializer,
    ParcelSerializer,
    ParcelGeoSerializer
)
from accounts.firebase_auth import verify_firebase_token

from django.contrib.gis.db.models.functions import Transform
from rest_framework.mixins import ListModelMixin

from rest_framework.viewsets import GenericViewSet
from rest_framework import viewsets, mixins


# for p in Parcel.objects.all():
#     geom = p.polygon
#     geom.srid = 25832
#     geom.transform(4326)
#     p.polygon = geom
#     p.save()


class ParcelGeoViewSet(viewsets.ModelViewSet):
    serializer_class = ParcelGeoSerializer

    def get_queryset(self):
        return Parcel.objects.annotate(
            # working if SRID is correct
            polygon_4326=Transform('polygon', 4326)
        )


# Parcel.objects.all().delete()


class FirebaseIsAuthenticated(BasePermission):
    """
    Custom permission class for Firebase authentication.
    """

    def has_permission(self, request, view):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            request.error_message = {
                "error": "Authentication header or Bearer token is missing."}
            return False

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            request.error_message = {
                "error": "Invalid or expired Firebase token."}
            return False

        request.user_email = decoded_token.get("email")
        request.user_role = decoded_token.get("role", "user")
        return True


class LanduseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Landuse instances.
    """

    queryset = Landuse.objects.all()
    serializer_class = LanduseSerializer


class ParcelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Parcel instances.
    """

    queryset = Parcel.objects.all()
    serializer_class = ParcelSerializer
    permission_classes = [FirebaseIsAuthenticated]
    basket = {}

    def perform_create(self, serializer):
        """
        Override the default create behavior to fetch `MarketUser` dynamically using Firebase UID.
        """
        auth_header = self.request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                {"error": "Authentication token is missing or invalid."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split("Bearer ")[1]

        # Verify the Firebase token
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            return Response(
                {"error": "Invalid or expired Firebase token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Fetch the Firebase UID and locate the corresponding MarketUser
        email = decoded_token.get("email")
        if not email:
            return Response(
                {"error": "Email not found in Firebase token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            market_user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response(
                {"error": "User associated with this Firebase UID not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Save the Parcel instance with the `created_by` field set
        serializer.save(created_by=market_user)

    @action(detail=True, methods=["get"], permission_classes=[FirebaseIsAuthenticated])
    def details(self, request, pk=None):
        """
        Retrieve details of a specific parcel.
        """
        try:
            parcel = self.get_object()
            serializer = self.get_serializer(parcel)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Parcel.DoesNotExist:
            return Response(
                {"error": "The specified parcel does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["post"], permission_classes=[FirebaseIsAuthenticated])
    def calculate_and_save(self, request):
        """
        Calculate data for a parcel and save it in the Report model.
        """
        parcel_id = request.data.get("parcel_id")
        parcel = Parcel.objects.filter(id=parcel_id).first()

        if not parcel:
            return Response(
                {"error": "The specified parcel does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = {
            "area": parcel.area_square_meters,
            "calculated_value": parcel.area_square_meters * 2,  # Example calculation
        }

        report = Report.objects.create(
            parcel=parcel, calculation_result=result)
        return Response(
            {
                "message": "Calculation completed and saved successfully.",
                "report_id": report.id,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], permission_classes=[FirebaseIsAuthenticated])
    def purchased_items(self, request):
        """
        Retrieve parcels purchased by the authenticated user and related transactions.
        """
        user_email = request.user_email
        purchased_parcels = Parcel.objects.filter(
            created_by__email=user_email, status="purchased"
        )
        serializer = self.get_serializer(purchased_parcels, many=True)

        # Retrieve successful transactions
        transactions = PaymentTransaction.objects.filter(
            user__email=user_email, status="success"
        )

        transactions_data = [
            {
                "transaction_id": txn.identifier,
                "amount": txn.amount,
                "currency": txn.currency,
                "created_at": txn.created_at,
            }
            for txn in transactions
        ]

        return Response(
            {
                "message": "Thank you for your purchase!",
                "purchased_parcels": serializer.data,
                "transactions": transactions_data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[FirebaseIsAuthenticated])
    def buy(self, request, pk=None):
        """
        Purchase a parcel.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                {"error": "Authentication token is missing or invalid."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            return Response(
                {"error": "Invalid or expired Firebase token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_email = decoded_token.get("email")
        if not user_email:
            return Response(
                {"error": "Email not found in Firebase token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            user = MarketUser.objects.get(email=user_email)
        except MarketUser.DoesNotExist:
            return Response(
                {"error": "User does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            parcel = self.get_object()
            if parcel.status == "purchased":
                return Response(
                    {"error": "This parcel has already been purchased."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            transaction_id = f"mock_txn_{parcel.id}_{user_email}"
            transaction_details = {
                "transaction_id": transaction_id,
                "amount": parcel.area_square_meters * 10,  # Example pricing logic
                "status": "completed",
                "user_email": user_email,
            }

            parcel.status = "purchased"
            parcel.save()

            return Response(
                {
                    "message": "Parcel purchased successfully.",
                    "parcel_id": parcel.id,
                    "transaction_details": transaction_details,
                },
                status=status.HTTP_200_OK,
            )
        except Parcel.DoesNotExist:
            return Response(
                {"error": "The specified parcel does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"], permission_classes=[FirebaseIsAuthenticated])
    def add_to_basket(self, request, pk=None):
        """
        Add a parcel to the basket for analysis.
        """
        try:
            # Ensure the parcel exists
            parcel = self.get_object()

            # Ensure the user is authenticated and retrieve their email
            user_email = getattr(request, "user_email", None)
            if not user_email:
                return Response({"error": "User email not found. Authentication is required."}, status=status.HTTP_401_UNAUTHORIZED)

            # Initialize the basket if it does not exist for the user
            if user_email not in self.basket:
                self.basket[user_email] = []

            # Add the parcel to the basket if not already present
            if parcel.id not in self.basket[user_email]:
                self.basket[user_email].append(parcel.id)
                return Response({"message": "Parcel added to basket."}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "Parcel is already in the basket."}, status=status.HTTP_400_BAD_REQUEST)

        except Parcel.DoesNotExist:
            # Handle case where the parcel does not exist
            return Response({"error": "Parcel not found."}, status=status.HTTP_404_NOT_FOUND)

        except AttributeError as e:
            # Handle case where `self.basket` is not defined or initialized
            return Response({"error": f"Basket attribute error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            # Generic error handling for unexpected exceptions
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], permission_classes=[FirebaseIsAuthenticated])
    def remove_from_basket(self, request, pk=None):
        """
        Remove a parcel from the basket.
        """
        try:
            user_email = request.user_email
            if user_email in self.basket:
                # Ensure pk is compared as the correct type (convert to int if stored IDs are integers)
                pk = int(pk) if pk is not None else None
                if pk in self.basket[user_email]:
                    self.basket[user_email].remove(pk)
                    return Response({"message": "Parcel removed from basket."}, status=status.HTTP_200_OK)
            return Response({"error": "Parcel not in basket."}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({"error": "Invalid parcel ID."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"], permission_classes=[FirebaseIsAuthenticated])
    def basket_summary(self, request):
        """
        Provide an overview of parcels in the basket, including totals and taxes.
        """
        user_email = request.user_email
        if user_email not in self.basket or not self.basket[user_email]:
            return Response({"message": "Basket is empty."}, status=status.HTTP_200_OK)

        parcels = Parcel.objects.filter(id__in=self.basket[user_email])
        total_area = sum(parcel.area_square_meters for parcel in parcels)
        total_cost = sum(Decimal(parcel.area_square_meters) * Decimal(10)
                         for parcel in parcels)  # Ensure total_cost is Decimal
        tax = total_cost * Decimal("0.2")  # Use Decimal for tax rate
        summary = {
            "total_parcels": len(parcels),
            "total_area": total_area,
            "total_cost": total_cost,
            "tax": tax,
            "final_total": total_cost + tax,
        }
        return Response({"basket": summary}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], permission_classes=[FirebaseIsAuthenticated])
    def apply_discount(self, request):
        """
        Apply a discount code to the total cost.
        """
        discount_code = request.data.get("discount_code")
        if not discount_code:
            return Response({"error": "Discount code is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Example discount validation logic
        # Use Decimal for discounts
        valid_codes = {"SAVE10": Decimal("0.1"), "SAVE20": Decimal("0.2")}
        discount = valid_codes.get(discount_code.upper())
        if not discount:
            return Response({"error": "Invalid discount code."}, status=status.HTTP_400_BAD_REQUEST)

        user_email = request.user_email
        if user_email not in self.basket or not self.basket[user_email]:
            return Response({"error": "Basket is empty."}, status=status.HTTP_400_BAD_REQUEST)

        parcels = Parcel.objects.filter(id__in=self.basket[user_email])
        total_cost = sum(Decimal(parcel.area_square_meters) * Decimal(10)
                         for parcel in parcels)  # Ensure total_cost is Decimal
        tax = total_cost * Decimal("0.2")  # Use Decimal for tax rate
        final_total = total_cost + tax
        discounted_total = final_total * (1 - discount)

        return Response(
            {
                "original_total": final_total,
                "discounted_total": discounted_total,
                "discount_applied": discount_code.upper(),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[FirebaseIsAuthenticated])
    def analyze_polygon(self, request, pk=None):
        """
        Analyze polygon data for a parcel.
        """
        try:
            parcel = self.get_object()
            if not parcel.polygon:
                return Response({"error": "Polygon data is missing."}, status=status.HTTP_400_BAD_REQUEST)

            # Calculate area using GeoDjango
            polygon = GEOSGeometry(parcel.polygon)
            area = polygon.area

            # Save the calculated area to the parcel
            parcel.area_square_meters = area
            parcel.save()

            return Response(
                {"message": "Polygon analyzed successfully.", "calculated_area": area},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"], permission_classes=[FirebaseIsAuthenticated])
    def my_parcels(self, request):
        """
        List all parcels created by the authenticated user.
        """
        user_email = request.user_email
        parcels = Parcel.objects.filter(created_by__email=user_email)
        serializer = self.get_serializer(parcels, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[FirebaseIsAuthenticated])
    def detailed_view(self, request, pk=None):
        """
        Retrieve detailed parcel data with conditional display based on purchase status.
        """
        try:
            # Get the parcel object
            parcel = self.get_object()
            user_email = request.user_email
            user = MarketUser.objects.get(email=user_email)

            # Check if the user has purchased the "Analyse Plus" report
            report_purchased = Report.objects.filter(
                parcel=parcel, visible_for="USER", purchase_type="analyse_plus").exists()

            # Prepare the response data
            data = {
                "id": parcel.id,
                "state_name": parcel.state_name,
                "district_name": parcel.district_name,
                "municipality_name": parcel.municipality_name,
                "land_use": parcel.land_use,
                "area_square_meters": parcel.area_square_meters,
                "polygon": parcel.polygon.geojson if parcel.polygon else None,
                "details": {
                    "stromnetz": "Full Details" if report_purchased else "Blurred",
                    "solarpark": "Full Details" if report_purchased else "Blurred",
                    "windenergie": "Full Details" if report_purchased else "Blurred",
                    "energiespeicher": "Full Details" if report_purchased else "Blurred",
                    "biodiversität": "Full Details" if report_purchased else "Blurred",
                },
                "actions": {
                    "request_offer": True,
                    "download_report": report_purchased,
                    "buy_analyse_plus": not report_purchased,
                },
            }

            if not report_purchased:
                data["error"] = "Analyse Plus needs to be purchased to access these details."

            return Response(data, status=status.HTTP_200_OK)
        except Parcel.DoesNotExist:
            return Response({"error": "Parcel does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_queryset(self):
        """
        Add filtering functionality for parcels.
        """
        queryset = super().get_queryset()
        state_name = self.request.query_params.get("state_name")
        district_name = self.request.query_params.get("district_name")
        min_area = self.request.query_params.get("min_area")
        max_area = self.request.query_params.get("max_area")

        if state_name:
            queryset = queryset.filter(state_name__icontains=state_name)
        if district_name:
            queryset = queryset.filter(district_name__icontains=district_name)
        if min_area:
            queryset = queryset.filter(area_square_meters__gte=min_area)
        if max_area:
            queryset = queryset.filter(area_square_meters__lte=max_area)

        return queryset


class ParcelOwnershipPermission(IsAuthenticated):
    """
    Custom permission to ensure users can only operate on their own parcels.
    """

    def has_object_permission(self, request, view, obj):
        # Ensure the object is a Parcel and check ownership
        return isinstance(obj, Parcel) and obj.created_by == request.user


class AreaOfferViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing AreaOffer instances.
    """
    queryset = AreaOffer.objects.all()
    serializer_class = AreaOfferSerializer
    permission_classes = [FirebaseIsAuthenticated]

    def perform_create(self, serializer):
        """
        Automatically associate the created offer with the current user.
        """
        user = self.request.user
        serializer.save(created_by=user)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve the details of an area offer.
        """
        offer = self.get_object()
        serializer = self.get_serializer(offer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"])
    def update_criteria(self, request, pk=None):
        """
        Update criteria such as title, description, or utilization.
        """
        offer = self.get_object()
        if offer.created_by != request.user:
            return Response(
                {"error": "You are not allowed to update this offer."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(
            offer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def upload_document(self, request, pk=None):
        """
        Upload a document for the specified AreaOffer.
        """
        try:
            offer = self.get_object()
        except AreaOffer.DoesNotExist:
            return Response({"error": "AreaOffer not found."}, status=status.HTTP_404_NOT_FOUND)

        document_file = request.FILES.get("document")
        if not document_file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Create a new document instance and link it to the AreaOffer
        AreaOfferDocuments.objects.create(offer=offer, document=document_file)

        return Response({"message": "Document uploaded successfully."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def prepare_offer(self, request, pk=None):
        """
        Prepare an offer with criteria and additional files.
        """
        offer = self.get_object()
        data = request.data
        serializer = self.get_serializer(offer, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """
        Deactivate an offer.
        """
        offer = self.get_object()
        if offer.created_by != request.user:
            return Response(
                {"error": "You are not allowed to deactivate this offer."},
                status=status.HTTP_403_FORBIDDEN,
            )
        offer.status = AreaOffer.OfferStatus.INACTIVE
        offer.save()
        return Response(
            {"message": "Offer deactivated successfully."},
            status=status.HTTP_200_OK,
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        user_email = self.request.user_email  # From Firebase authentication
        if user_email:
            # Limit to user's offers
            queryset = queryset.filter(created_by__email=user_email)
        return queryset

    def list(self, request, *args, **kwargs):
        """
        List offers for the logged-in user with proper messaging for empty results.
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Check if the queryset is empty
        if not queryset.exists():
            return Response(
                {"message": "No offers found."},
                status=status.HTTP_200_OK,
            )

        # Paginate if needed
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Serialize and return data
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AreaOfferDocumentsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing AreaOfferDocuments instances.
    """

    queryset = AreaOfferDocuments.objects.all()
    serializer_class = AreaOfferDocumentsSerializer
