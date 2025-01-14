from decimal import Decimal
from django.conf import settings
from .models import BasketItem


def get_basket_summary(user):
    basket_items = BasketItem.objects.filter(
        user=user).select_related("parcel")
    if not basket_items.exists():
        raise ValueError("Basket is empty.")

    analyse_plus_rate = settings.ANALYSE_PLUS_RATE  # Rate per square meter
    tax_rate = Decimal(settings.TAX_RATE)  # e.g., 0.19 for 19%

    number_of_items = basket_items.count()
    total_cost = number_of_items * analyse_plus_rate
    tax_amount = total_cost * tax_rate
    subtotal = total_cost + tax_amount

    # Format output
    return {
        "number_of_items": number_of_items,
        "cost_per_item": f"{analyse_plus_rate:,.2f}",
        "sum_of_items": f"{total_cost:,.2f}",
        "tax_in_percent": int(tax_rate * 100),
        "tax_amount": f"{tax_amount:,.2f}",
        "subtotal": f"{subtotal:,.2f}",
    }
