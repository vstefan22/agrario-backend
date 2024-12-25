"""Views for the Offers application.

Provides endpoints for managing land use, parcels, area offers, and associated documents.
"""

from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from accounts.models import MarketUser

from .models import (
    AreaOffer,
    AreaOfferConfirmation,
    AreaOfferDocuments,
    Landuse,
    Parcel,
    Report,
)
from .serializers import (
    AreaOfferDocumentsSerializer,
    AreaOfferSerializer,
    AuctionPlacementSerializer,
    LanduseSerializer,
    ParcelSerializer,
)
from accounts.firebase_auth import verify_firebase_token


class FirebaseIsAuthenticated(BasePermission):
    """
    Custom permission class for Firebase authentication.
    """
    def has_permission(self, request, view):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return False

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            return False

        # Attach user info to the request object for further use
        request.user_email = decoded_token.get("email")
        request.user_role = decoded_token.get("role", "user")  # Assume default role
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
        # Retrieve the Firebase token from the request headers
        auth_header = self.request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise PermissionDenied(detail="Authentication token is missing or invalid.")

        token = auth_header.split("Bearer ")[1]

        # Verify the Firebase token
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            raise PermissionDenied(detail="Invalid or expired Firebase token.")

        # Fetch the Firebase UID and locate the corresponding MarketUser
        firebase_uid = decoded_token.get("uid")
        email = decoded_token.get("email")
        if not email:
            raise PermissionDenied(detail="Email not found in Firebase token.")

        try:
            market_user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            raise PermissionDenied(detail="User associated with this Firebase UID not found.")

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

        report = Report.objects.create(parcel=parcel, calculation_result=result)
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
        Retrieve parcels purchased by the authenticated user.
        """
        user_email = request.user_email
        purchased_parcels = Parcel.objects.filter(created_by__email=user_email, status="purchased")
        serializer = self.get_serializer(purchased_parcels, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[FirebaseIsAuthenticated])
    def buy(self, request, _pk=None):
        """
        Purchase a parcel.
        """
        user_email = request.user_email
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


class AreaOfferViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing AreaOffer instances.
    """

    queryset = AreaOffer.objects.all()
    serializer_class = AreaOfferSerializer

    @action(detail=True, methods=["post"], url_path="confirm", permission_classes=[FirebaseIsAuthenticated])
    def confirm_offer(self, request, _pk=None):
        """
        Confirm an area offer.
        """
        offer = self.get_object()
        if AreaOfferConfirmation.objects.filter(offer=offer).exists():
            return Response(
                {"error": "The specified offer has already been confirmed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        confirmation = AreaOfferConfirmation.objects.create(
            offer=offer, confirmed_by_email=request.user_email
        )
        return Response(
            {
                "message": "Offer confirmed successfully.",
                "confirmation_id": confirmation.id,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], permission_classes=[FirebaseIsAuthenticated])
    def place_auction(self, request):
        """
        Place an auction for an area offer.
        """
        if request.user_role != "landowner":
            return Response(
                {"error": "Only landowners are permitted to place auctions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AuctionPlacementSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AreaOfferDocumentsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing AreaOfferDocuments instances.
    """

    queryset = AreaOfferDocuments.objects.all()
    serializer_class = AreaOfferDocumentsSerializer
