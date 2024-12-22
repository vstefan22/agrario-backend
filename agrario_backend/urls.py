from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Define the OpenAPI Info object
swagger_info = openapi.Info(
    title="Agrario API",
    default_version='v1',
    description="API documentation for the Agrario Energy Marketplace",
    terms_of_service="https://www.google.com/policies/terms/",
    contact=openapi.Contact(email="support@agrario.com"),
    license=openapi.License(name="MIT License"),
)

# Use swagger_info in the schema view
schema_view = get_schema_view(
    swagger_info,
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('api/accounts/', include('accounts.urls')),
    path('api/offers/', include('offers.urls')),
    path('swagger/', schema_view.with_ui('swagger',
         cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc',
         cache_timeout=0), name='schema-redoc'),
]
