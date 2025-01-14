from django.urls import path
from .views import CreateStripePaymentView, StripeWebhookView

urlpatterns = [
    path("create-payment/", CreateStripePaymentView.as_view(), name="create-payment"),
    path("stripe-webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
