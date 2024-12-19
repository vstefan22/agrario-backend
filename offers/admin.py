"""
Admin configuration for the Offers application.
"""

from django.contrib import admin
from .models import Landuse, Parcel, AreaOffer, AreaOfferDocuments, AreaOfferConfirmation, AreaOfferAdministration


@admin.register(Landuse)
class LanduseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name',)


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'landuse', 'area')
    search_fields = ('owner__username', 'landuse__name')
    list_filter = ('landuse',)


@admin.register(AreaOffer)
class AreaOfferAdmin(admin.ModelAdmin):
    list_display = ('id', 'parcel', 'price', 'is_active', 'created_at')
    search_fields = ('parcel__owner__username', 'price')
    list_filter = ('is_active',)


@admin.register(AreaOfferDocuments)
class AreaOfferDocumentsAdmin(admin.ModelAdmin):
    list_display = ('id', 'offer', 'document', 'uploaded_at')
    search_fields = ('offer__parcel__owner__username',)


@admin.register(AreaOfferConfirmation)
class AreaOfferConfirmationAdmin(admin.ModelAdmin):
    list_display = ('id', 'offer', 'confirmed_by', 'confirmed_at')
    search_fields = ('offer__parcel__owner__username', 'confirmed_by__username')


@admin.register(AreaOfferAdministration)
class AreaOfferAdministrationAdmin(admin.ModelAdmin):
    list_display = ('id', 'offer', 'notes', 'created_at')
    search_fields = ('offer__parcel__owner__username', 'notes')
