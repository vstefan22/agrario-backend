"""
Views for the Offers application.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated 
from .models import (
    Landuse,
    Parcel,
    AreaOffer, 
    AreaOfferDocuments, 
    AreaOfferConfirmation, 
    AreaOfferAdministration,
    Report
    )

from .serializers import (
    LanduseSerializer,
    ParcelSerializer,
    AreaOfferSerializer,
    AreaOfferDocumentsSerializer,
    AreaOfferConfirmationSerializer,
    AreaOfferAdministrationSerializer,
    AuctionPlacementSerializer,
    ReportSerializer
)


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

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def calculate_and_save(self, request):
        """
        API endpoint to calculate data and save it in the report table.
        """
        # Extract data from the request
        parcel_id = request.data.get("parcel_id")
        parcel = Parcel.objects.filter(id=parcel_id).first()

        if not parcel:
            return Response({"error": "Parcel not found."}, status=status.HTTP_404_NOT_FOUND)

        # Perform calculations (Example logic)
        result = {
            "area": parcel.area,
            "calculated_value": parcel.area * 2,  # Replace with actual calculation logic
        }

        # Save the result in the Report table
        report = Report.objects.create(parcel=parcel, calculation_result=result)

        return Response({"message": "Calculation completed and saved.", "report_id": report.id}, status=status.HTTP_201_CREATED)


class AreaOfferViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing AreaOffer instances.
    """
    queryset = AreaOffer.objects.all()
    serializer_class = AreaOfferSerializer

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm_offer(self, request, pk=None):
        """
        Custom action to confirm an offer.
        """
        offer = self.get_object()
        if AreaOfferConfirmation.objects.filter(offer=offer).exists():
            return Response({"error": "Offer is already confirmed."}, status=status.HTTP_400_BAD_REQUEST)

        confirmation = AreaOfferConfirmation.objects.create(
            offer=offer,
            confirmed_by=request.user
        )
        return Response(
            {"message": "Offer confirmed successfully.", "confirmation_id": confirmation.id},
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def place_auction(self, request):
        if request.user.role != 'landowner':
            return Response({"error": "Only landowners can place auctions."}, status=status.HTTP_403_FORBIDDEN)
        serializer = AuctionPlacementSerializer(data=request.data, context={'request': request})
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