from decimal import Decimal
from django.db.models import Sum
from .models import BasketItem
from django.conf import settings

def get_basket_summary(user):
    basket_items = BasketItem.objects.filter(user=user).select_related("parcel")
    if not basket_items.exists():
        raise ValueError("Basket is empty.")
    
    # Assuming each parcel has a cost per square meter rate
    total_cost = sum(
        Decimal(item.parcel.area_square_meters) * settings.ANALYSE_PLUS_RATE
        for item in basket_items
    )
    parcel_ids = basket_items.values_list('parcel__id', flat=True)

    return {
        "total_cost": total_cost,
        "parcel_ids": list(parcel_ids),
    }