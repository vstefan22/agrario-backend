"""
Views for the Offers application.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Landuse, Parcel, AreaOffer, AreaOfferDocuments, AreaOfferConfirmation, AreaOfferAdministration
from .serializers import (
    LanduseSerializer,
    ParcelSerializer,
    AreaOfferSerializer,
    AreaOfferDocumentsSerializer,
    AreaOfferConfirmationSerializer,
    AreaOfferAdministrationSerializer,
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
