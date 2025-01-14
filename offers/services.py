from decimal import Decimal
from django.db.models import Sum
from .models import BasketItem
from django.conf import settings

from django.core.serializers.json import DjangoJSONEncoder
from accounts.serializers import LandownerSerializer  # Assuming you have a serializer for MarketUser

def get_basket_summary(user):
    basket_items = BasketItem.objects.filter(user=user).select_related("parcel")
    if not basket_items.exists():
        raise ValueError("Basket is empty.")

    # Calculate the total cost based on area and rate
    total_cost = sum(
        Decimal(item.parcel.area_square_meters) * settings.ANALYSE_PLUS_RATE
        for item in basket_items
    )

    # Collect detailed information for each parcel
    parcels = [
        {
            "id": item.parcel.id,
            "state_name": item.parcel.state_name,
            "zipcode": item.parcel.zipcode,
            "district_name": item.parcel.district_name,
            "municipality_name": item.parcel.municipality_name,
            "cadastral_area": item.parcel.cadastral_area,
            "cadastral_parcel": item.parcel.cadastral_parcel,
            "plot_number_main": item.parcel.plot_number_main,
            "plot_number_secondary": item.parcel.plot_number_secondary,
            "land_use": item.parcel.land_use,
            "area_square_meters": f"{item.parcel.area_square_meters:,}",  # Format with commas
            "created_by": LandownerSerializer(item.parcel.created_by).data,  # Serialize MarketUser
            "polygon": item.parcel.polygon.geojson if item.parcel.polygon else None
        }
        for item in basket_items
    ]

    return {
        "total_cost": f"{total_cost:,.2f} €",  # Format with commas and two decimal points
        "parcels": parcels,
    }
