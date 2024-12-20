"""
URLs for the Offers application.

Routes API endpoints for land use, parcels, and area offers.
"""

from rest_framework.routers import DefaultRouter
from .views import LanduseViewSet, ParcelViewSet, AreaOfferViewSet

router = DefaultRouter()
router.register(r'landuse', LanduseViewSet, basename='landuse')
router.register(r'parcels', ParcelViewSet, basename='parcels')
router.register(r'area_offers', AreaOfferViewSet, basename='area-offers')

urlpatterns = router.urls
