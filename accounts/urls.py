"""URL configuration for the Marketplace application.

Defines routes for user management, authentication, and role-specific dashboards.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ConfirmEmailView,
    LoginView,
    MarketUserProfileView,
    MarketUserViewSet,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RoleDashboardView,
    stripe_webhook,
)

# Create a router and register the MarketUser viewset
router = DefaultRouter()
router.register(r"users", MarketUserViewSet, basename="market-user")

# Define urlpatterns with additional routes
urlpatterns = [
    path(
        "confirm-email/<uidb64>/<token>/",
        ConfirmEmailView.as_view(),
        name="confirm-email",
    ),
    path("login/", LoginView.as_view(), name="login"),
    path("dashboard/", RoleDashboardView.as_view(), name="dashboard"),
    path("webhook/stripe/", stripe_webhook, name="stripe-webhook"),
    path("profile/", MarketUserProfileView.as_view(), name="profile"),
    path(
        "password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
] + router.urls
