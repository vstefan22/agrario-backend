"""URL configuration for the Marketplace application.

Defines routes for user management, authentication, and role-specific dashboards.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    LoginView,
    MarketUserProfileView,
    MarketUserViewSet,
    FirebasePasswordResetRequestView,
    RoleDashboardView,
)

# Create a router and register the MarketUser viewset
router = DefaultRouter()
router.register(r"users", MarketUserViewSet, basename="market-user")
# router.register(r"profile", MarketUserProfileView, basename="profile")

# Define urlpatterns with additional routes
urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("dashboard/", RoleDashboardView.as_view(), name="dashboard"),
    path("profile/", MarketUserProfileView.as_view({'get': 'retrieve', 'patch': 'partial_update'}), name="profile"),
    path(
        "password-reset/",
        FirebasePasswordResetRequestView.as_view(),
        name="password-reset-request",
    )
] + router.urls