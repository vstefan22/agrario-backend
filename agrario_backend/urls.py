"""
URL configuration for Agrario project.

This module defines the URL routes for the project, including
API endpoints for accounts, offers, and Swagger/Redoc documentation.
"""

from django.urls import include, path
from django.contrib import admin
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# Define the OpenAPI Info object
swagger_info = openapi.Info(
    title="Agrario API",
    default_version="v1",
    description="API documentation for the Agrario Energy Marketplace",
    terms_of_service="https://www.google.com/policies/terms/",
    contact=openapi.Contact(email="support@agrario.com"),
    license=openapi.License(name="MIT License"),
)

# Schema view configuration
SchemaView = get_schema_view(
    swagger_info,
    public=True,
    permission_classes=[permissions.AllowAny],
)

# URL patterns
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path("api/offers/", include("offers.urls")),
    path(
        "swagger/",
        SchemaView.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", SchemaView.with_ui("redoc",
         cache_timeout=0), name="schema-redoc"),
]
