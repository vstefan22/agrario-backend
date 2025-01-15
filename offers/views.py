"""Views for the Offers application.

Provides endpoints for managing land use, parcels, area offers, and associated documents.
"""

import logging
from stripe.error import InvalidRequestError
from django.conf import settings
from decimal import Decimal
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.db.models.functions import Transform
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .services import get_basket_summary
from accounts.models import MarketUser
from payments.models import PaymentTransaction
from reports.models import Report
from .models import (
    AreaOffer,
    AreaOfferConfirmation,
    AreaOfferDocuments,
    Landuse,
    Parcel,
    BasketItem,
    Watchlist
)
from .serializers import (
    AreaOfferDocumentsSerializer,
    AreaOfferSerializer,
    AreaOfferConfirmationSerializer,
    LanduseSerializer,
    ParcelSerializer,
    ParcelGeoSerializer,
    WatchlistSerializer,
    BasketItemSerializer
)
from accounts.firebase_auth import verify_firebase_token

from django.contrib.gis.db.models.functions import Transform
import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY


class ParcelGeoViewSet(viewsets.ModelViewSet):
    serializer_class = ParcelGeoSerializer

    def get_queryset(self):
        return Parcel.objects.annotate(
            # working if SRID is correct
            polygon_4326=Transform('polygon', 4326)
        )


# Configure logger
logger = logging.getLogger(__name__)


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

    def perform_create(self, serializer):
        """
        Override the default create behavior to fetch `MarketUser` dynamically using Firebase UID.
        """
        auth_header = self.request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise PermissionDenied(
                "Authentication token is missing or invalid.")

        token = auth_header.split("Bearer ")[1]

        # Verify the Firebase token
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            raise PermissionDenied("Invalid or expired Firebase token.")

        # Fetch the Firebase UID and locate the corresponding MarketUser
        email = decoded_token.get("email")
        if not email:
            raise PermissionDenied("Email not found in Firebase token.")

        try:
            market_user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            raise PermissionDenied(
                "User associated with this Firebase UID not found.")

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

    def calculate_and_save(self, request):
        parcel_id = request.data.get("parcel_id")
        parcel = Parcel.objects.filter(id=parcel_id).first()

        if not parcel:
            return Response(
                {"error": "The specified parcel does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = {
            "area": parcel.area_square_meters,
            "calculated_value": parcel.area_square_meters * 1.2,  # Example calculation
        }

        # Save the report
        report = Report.objects.create(
            parcel=parcel, calculation_result=result)

        return Response(
            {
                "message": "Calculation completed and saved successfully.",
                "report_id": report.id,
            },
            status=status.HTTP_201_CREATED,
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
        Add a parcel to the basket stored in the database.
        """
        try:
            parcel = self.get_object()
            BasketItem.objects.get_or_create(user=request.user, parcel=parcel)
            return Response({"message": "Parcel added to basket."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["delete"], permission_classes=[FirebaseIsAuthenticated])
    def remove_from_basket(self, request, pk=None):
        """
        Remove a parcel from the basket stored in the database.
        """
        try:
            parcel = self.get_object()
            basket_item = BasketItem.objects.filter(
                user=request.user, parcel=parcel).first()
            if not basket_item:
                return Response({"error": "Parcel not in basket."}, status=status.HTTP_400_BAD_REQUEST)
            basket_item.delete()
            return Response({"message": "Parcel removed from basket."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"], url_path="basket-items", permission_classes=[FirebaseIsAuthenticated])
    def basket_items(self, request):
        """
        Retrieve all basket items for the authenticated user.
        """
        try:
            user = request.user
            basket_items = BasketItem.objects.filter(user=user)

            if not basket_items.exists():
                return Response({"message": "Your basket is empty."}, status=status.HTTP_200_OK)

            parcels = [item.parcel for item in basket_items]
            serializer = BasketItemSerializer(basket_items, many=True)

            return Response({
                "message": "Basket items retrieved successfully.",
                "basket_items": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"], permission_classes=[FirebaseIsAuthenticated])
    def basket_summary(self, request):
        """
        Provide an overview of parcels in the basket using the basket service.
        """
        try:
            summary = get_basket_summary(request.user)
            return Response(summary, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        try:
            # Validate the discount code with Stripe
            coupon = stripe.Coupon.retrieve(discount_code)
            if not coupon.valid:
                return Response({"error": "Invalid or expired discount code."}, status=status.HTTP_400_BAD_REQUEST)
        except InvalidRequestError:
            return Response({"error": "Invalid discount code."}, status=status.HTTP_400_BAD_REQUEST)

        user_email = request.user_email
        if user_email not in self.basket or not self.basket[user_email]:
            return Response({"error": "Basket is empty."}, status=status.HTTP_400_BAD_REQUEST)

        summary = get_basket_summary(request.user)
        final_total = summary['subtota']
        discount_amount = Decimal(coupon.percent_off or 0) / \
            100 if coupon.percent_off else Decimal(
                coupon.amount_off or 0) / 100
        discounted_total = final_total - discount_amount

        return Response(
            {
                "original_total": final_total,
                "discounted_total": discounted_total,
                "discount_applied": discount_code.upper(),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], permission_classes=[FirebaseIsAuthenticated])
    def order_confirmation(self, request):
        """
        Retrieve details of the latest order for the authenticated user.
        """
        user = request.user

        # Get the latest successful transaction for the user
        transaction = PaymentTransaction.objects.filter(
            user=user, status="success").order_by("-created_at").first()

        if not transaction:
            return Response({"error": "No successful transactions found."}, status=status.HTTP_404_NOT_FOUND)

        # Get parcels associated with the transaction
        parcel_ids = transaction.stripe_payment_intent.metadata.get(
            # Adjust if metadata is structured differently
            "parcel_ids", "").split(",")
        parcels = Parcel.objects.filter(id__in=parcel_ids)

        # Prepare response data
        parcel_data = [
            {"id": parcel.id, "state_name": parcel.state_name,
                "area_square_meters": parcel.area_square_meters}
            for parcel in parcels
        ]

        response_data = {
            "transaction_id": transaction.identifier,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "payment_method": transaction.payment_method,
            "created_at": transaction.created_at,
            "parcels": parcel_data,
            "message": "Thank you for your purchase! Detailed analysis results will be available within 24 hours.",
        }

        return Response(response_data, status=status.HTTP_200_OK)

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
        Retrieve detailed parcel data with associated offer information using serializers.
        """
        try:
            parcel = get_object_or_404(Parcel, pk=pk)
            user_email = request.user_email
            user = MarketUser.objects.get(email=user_email)

            if user.role != "developer":
                return Response(
                    {"error": "Only project developers can view detailed parcel data."},
                    status=status.HTTP_403_FORBIDDEN
                )

            report_purchased = Report.objects.filter(
                identifier=parcel.id, visible_for="USER", purchase_type="analyse_plus"
            ).exists()

            parcel_serializer = ParcelSerializer(
                parcel, context={'request': request})

            offer_data = {}
            if parcel.appear_in_offer:
                offer_serializer = AreaOfferSerializer(
                    parcel.appear_in_offer, context={'request': request})
                offer_data = offer_serializer.data

            if not report_purchased:
                parcel_data = parcel_serializer.data
                parcel_data["analyze_plus"] = report_purchased
            else:
                parcel_data = parcel_serializer.data

            response_data = {
                "parcel": parcel_data,
                "offer": offer_data
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Parcel.DoesNotExist:
            return Response({"error": "Parcel does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_queryset(self):
        """
        Add filtering functionality for parcels.
        """
        queryset = super().get_queryset()

        municipality_name = self.request.query_params.get("municipality_name")
        cadastral_area = self.request.query_params.get("cadastral_area")
        communal_district = self.request.query_params.get("communal_district")
        cadastral_parcel = self.request.query_params.get("cadastral_parcel")

        if municipality_name:
            queryset = queryset.filter(
                municipality_name__icontains=municipality_name)
        if cadastral_area:
            queryset = queryset.filter(
                cadastral_area__icontains=cadastral_area)
        if communal_district:
            queryset = queryset.filter(
                communal_district__icontains=communal_district)
        if cadastral_parcel:
            queryset = queryset.filter(
                cadastral_parcel__icontains=cadastral_parcel)

        return queryset

    @action(detail=True, methods=["post"], url_path="add-to-watchlist", permission_classes=[FirebaseIsAuthenticated])
    def add_to_watchlist(self, request, pk=None):
        """
        Add a parcel to the user's watchlist using parcel ID from the URL.
        """
        try:
            # Dohvatanje parcele preko ID-a iz URL-a (pk)
            parcel = Parcel.objects.get(id=pk)
            watchlist_item, created = Watchlist.objects.get_or_create(
                user=request.user, parcel=parcel
            )
            if not created:
                return Response({"error": "Parcel is already in the watchlist."}, status=status.HTTP_400_BAD_REQUEST)

            serializer = WatchlistSerializer(watchlist_item)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Parcel.DoesNotExist:
            return Response({"error": "Parcel not found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path="remove-from-watchlist", permission_classes=[FirebaseIsAuthenticated])
    def remove_from_watchlist(self, request, pk=None):
        """
        Remove a parcel from the user's watchlist using parcel ID from the URL.
        """
        try:
            parcel = Parcel.objects.get(id=pk)
            watchlist_item = Watchlist.objects.get(
                user=request.user, parcel=parcel)
            watchlist_item.delete()
            return Response({"message": "Parcel removed from watchlist."}, status=status.HTTP_200_OK)
        except Parcel.DoesNotExist:
            return Response({"error": "Parcel not found."}, status=status.HTTP_404_NOT_FOUND)
        except Watchlist.DoesNotExist:
            return Response({"error": "Parcel not in the watchlist."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], url_path="watchlist", permission_classes=[FirebaseIsAuthenticated])
    def list_watchlist(self, request):
        """
        List all parcels in the user's watchlist with criteria from AreaOffer.
        """
        watchlist_items = Watchlist.objects.filter(
            user=request.user).values_list('parcel', flat=True)
        parcels_in_watchlist = Parcel.objects.filter(id__in=watchlist_items)

        response_data = []

        for parcel in parcels_in_watchlist:
            parcel_data = ParcelSerializer(
                parcel, context={'request': request}).data
            criteria_data = parcel.appear_in_offer.criteria if parcel.appear_in_offer else {}

            response_data.append({
                "parcel": parcel_data,
                "criteria": criteria_data
            })

        return Response({"parcels": response_data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="registered-parcels", permission_classes=[FirebaseIsAuthenticated])
    def registered_parcels(self, request):
        """
        Vraća sve parcele koje imaju vezan AreaOffer sa odvojenim kriterijumima.
        """
        parcels_with_offer = Parcel.objects.filter(
            appear_in_offer__isnull=False)
        response_data = []

        for parcel in parcels_with_offer:
            parcel_data = ParcelSerializer(
                parcel, context={'request': request}).data
            criteria_data = parcel.appear_in_offer.criteria if parcel.appear_in_offer else {}

            response_data.append({
                "parcel": parcel_data,
                "criteria": criteria_data
            })

        return Response({"parcels": response_data}, status=status.HTTP_200_OK)


class ParcelOwnershipPermission(IsAuthenticated):
    """
    Custom permission to ensure users can only operate on their own parcels.
    """

    def has_object_permission(self, request, view, obj):
        # Ensure the object is a Parcel and check ownership
        return isinstance(obj, Parcel) and obj.created_by == request.user


class AreaOfferViewSet(viewsets.ModelViewSet):
    queryset = AreaOffer.objects.all()
    serializer_class = AreaOfferSerializer
    permission_classes = [FirebaseIsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        """
        Handle parcel associations and dynamically set the created_by field.
        """
        # Save the AreaOffer with the created_by field dynamically set
        area_offer = serializer.save(created_by=self.request.user)

        # Associate parcels if parcel_ids are provided
        parcel_ids = self.request.data.get("parcel_ids", [])
        if parcel_ids:
            parcels = Parcel.objects.filter(
                id__in=parcel_ids, appear_in_offer__isnull=True)
            for parcel in parcels:
                parcel.appear_in_offer = area_offer
                parcel.save()  # Explicitly save each parcel

        # Refresh the instance to include updated reverse relationships
        area_offer.refresh_from_db()

        # Handle uploaded documents
        self._handle_uploaded_files(area_offer)

    def perform_create(self, serializer):
        """
        Handle parcel associations and dynamically set the created_by field.
        """
        # Save the AreaOffer with the created_by field dynamically set
        area_offer = serializer.save(created_by=self.request.user)

        # Associate parcels if parcel_ids are provided
        parcel_ids = self.request.data.get("parcel_ids", [])
        print("parcel_ids         ======>       ", parcel_ids)
        if parcel_ids:
            parcels = Parcel.objects.filter(
                id__in=parcel_ids, appear_in_offer__isnull=True)
            print("parcels", parcels)
            for parcel in parcels:
                print("for parcel in parcels: ", parcel)
                parcel.appear_in_offer = area_offer
                print("parcel", parcel)
                print("appear_in_offer", parcel.appear_in_offer)
                parcel.save()  # Save each parcel explicitly to update the relationship

        # Refresh the instance to include updated reverse relationships
        area_offer = AreaOffer.objects.prefetch_related(
            "parcels").get(pk=area_offer.pk)
        print("area_offer", area_offer)

        # Handle uploaded documents
        self._handle_uploaded_files(area_offer)

    def get_queryset(self):
        """
        Include parcels in the queryset to ensure the relationship is fetched.
        """
        queryset = super().get_queryset()
        print("queryset", queryset)
        return queryset.prefetch_related("parcels")

    def _handle_uploaded_files(self, offer):
        """
        Handles uploaded files for an AreaOffer.
        """
        files = self.request.FILES.getlist('documents')
        for file in files:
            AreaOfferDocuments.objects.create(offer=offer, document=file)

    @action(detail=False, methods=["get"], url_path="active_offers", permission_classes=[FirebaseIsAuthenticated])
    def list_active_offers(self, request):
        """
        Return all active area offers with status 'A'.
        """
        # staviti kad skontamo sa statusima sta kako gde
        # active_offers = AreaOffer.objects.filter(status=AreaOffer.OfferStatus.ACTIVE)
        active_offers = AreaOffer.objects.all()

        serializer = AreaOfferSerializer(
            active_offers, many=True, context={'request': request})

        return Response({"offers": serializer.data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="submit_offer", permission_classes=[FirebaseIsAuthenticated])
    def submit_offer(self, request, pk=None):
        """
        Developer submits an offer for an auction and confirms it.
        """
        try:
            offer = get_object_or_404(AreaOffer, identifier=pk)

            if hasattr(offer, 'confirmation'):
                return Response({"error": "This offer has already been confirmed."}, status=status.HTTP_400_BAD_REQUEST)

            user = request.user

            if user.role != "developer":
                return Response({"error": "Only developers can submit offers."}, status=status.HTTP_403_FORBIDDEN)

            confirmation_data = request.data.copy()
            confirmation_data["offer"] = str(offer.identifier)
            confirmation_data["confirmed_by"] = str(user.id)

            serializer = AreaOfferConfirmationSerializer(
                data=confirmation_data)

            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Offer successfully submitted and confirmed."}, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except AreaOffer.DoesNotExist:
            return Response({"error": "Offer does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"], url_path="submitted-offers", permission_classes=[FirebaseIsAuthenticated])
    def submitted_offers(self, request):
        try:
            user = request.user
            user_confirmations = AreaOfferConfirmation.objects.filter(
                confirmed_by=user)

            response_data = []

            for confirmation in user_confirmations:
                offer = confirmation.offer

                offer_serializer = AreaOfferSerializer(
                    offer, context={'request': request})

                confirmation_serializer = AreaOfferConfirmationSerializer(
                    confirmation, context={'request': request})

                response_data.append({
                    "offer": offer_serializer.data,
                    "offer_confirmation": confirmation_serializer.data
                })

            return Response({"offers": response_data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["get"], url_path="submitted-offers", permission_classes=[FirebaseIsAuthenticated])
    def retrieve_submitted_offer(self, request, pk=None):

        try:
            offer_confirmation = get_object_or_404(
                AreaOfferConfirmation, identifier=pk)

            if offer_confirmation.confirmed_by != request.user:
                return Response(
                    {"error": "You do not have permission to access this offer confirmation."},
                    status=status.HTTP_403_FORBIDDEN
                )

            offer = offer_confirmation.offer

            offer_serializer = AreaOfferSerializer(
                offer, context={'request': request})

            confirmation_serializer = AreaOfferConfirmationSerializer(
                offer_confirmation, context={'request': request})

            response_data = {
                "offer": offer_serializer.data,
                "offer_confirmation": confirmation_serializer.data
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except AreaOfferConfirmation.DoesNotExist:
            return Response({"error": "Offer confirmation does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["patch"], url_path="edit-submitted-offers", permission_classes=[FirebaseIsAuthenticated])
    def update_submitted_offer(self, request, pk=None):

        try:
            offer_confirmation = get_object_or_404(
                AreaOfferConfirmation, identifier=pk)

            if offer_confirmation.confirmed_by != request.user:
                return Response(
                    {"error": "You do not have permission to edit this offer confirmation."},
                    status=status.HTTP_403_FORBIDDEN
                )

            serializer = AreaOfferConfirmationSerializer(
                offer_confirmation, data=request.data, partial=True
            )

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"message": "Offer confirmation successfully updated."},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except AreaOfferConfirmation.DoesNotExist:
            return Response({"error": "Offer confirmation does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AreaOfferDocumentsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing AreaOfferDocuments instances.
    """

    queryset = AreaOfferDocuments.objects.all()
    serializer_class = AreaOfferDocumentsSerializer
