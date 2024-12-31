"""URLs for the Offers application.

Routes API endpoints for land use, parcels, and area offers.
"""

from rest_framework.routers import DefaultRouter

from .views import (
    AreaOfferDocumentsViewSet,
    AreaOfferViewSet,
    LanduseViewSet,
    ParcelViewSet,
)

# Initialize the router and register viewsets
router = DefaultRouter()
router.register(r"landuse", LanduseViewSet, basename="landuse")
router.register(r"parcels", ParcelViewSet, basename="parcels")
router.register(r"area_offers", AreaOfferViewSet, basename="area-offers")
router.register(
    r"area_offer_documents", AreaOfferDocumentsViewSet, basename="area-offer-documents"
)

# Define URL patterns
urlpatterns = router.urls