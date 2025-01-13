"""Admin configuration for the Offers application.

This module defines how the Offers-related models are displayed and managed
within the Django admin interface.
"""

from django.contrib import admin

from .models import (
    AreaOffer,
    AreaOfferAdministration,
    AreaOfferConfirmation,
    Landuse,
    Parcel,
)


@admin.register(Landuse)
class LanduseAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Landuse model.
    """

    list_display = ("id", "name", "description")
    search_fields = ("name",)


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Parcel model.
    """

    list_display = ("id", "state_name", "district_name", "municipality_name")
    search_fields = ("district_name", "state_name")
    list_filter = ("state_name",)


@admin.register(AreaOffer)
class AreaOfferAdmin(admin.ModelAdmin):
    """
    Admin configuration for AreaOffer model.
    """
    list_display = (
        "identifier",  # Unique identifier
        "offer_number",  # Offer number
        "status",  # Current status of the offer
        "utilization",  # Utilization type (Sale, Lease, etc.)
        "available_from",  # Availability date
        "created_by",  # Landowner who created the offer
    )
    list_filter = (
        "status",  # Filter by status
        "utilization",  # Filter by utilization type
        "available_from",  # Filter by availability date
    )
    search_fields = ("offer_number", "available_from")  # Search fields
    ordering = ("-available_from",)  # Default ordering


class AreaOfferDocumentsAdmin(admin.ModelAdmin):
    """
    Admin configuration for the AreaOfferDocuments model.
    """

    list_display = ("id", "get_offer", "document", "uploaded_at")

    def get_offer(self, obj):
        """
        Display the related offer for the document.
        """
        return obj.offer.str()

    get_offer.short_description = "Offer"


@admin.register(AreaOfferConfirmation)
class AreaOfferConfirmationAdmin(admin.ModelAdmin):
    """
    Admin configuration for the AreaOfferConfirmation model.
    """

    list_display = ("id", "offer", "confirmed_by", "confirmed_at")
    search_fields = ("offer__parcel__owner__username", "confirmed_by__username")


@admin.register(AreaOfferAdministration)
class AreaOfferAdministrationAdmin(admin.ModelAdmin):
    """
    Admin configuration for the AreaOfferAdministration model.
    """

    list_display = ("id", "offer", "notes", "created_at")
    search_fields = ("offer__parcel__owner__username", "notes")
