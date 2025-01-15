from django.urls import path
from .views import StripeSessionView, StripeWebhookView

urlpatterns = [
    path("create-payment/", StripeSessionView.as_view(), name="create-payment"),
    path("stripe-webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
