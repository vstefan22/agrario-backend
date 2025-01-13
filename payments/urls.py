from django.urls import path
from .views import CreateStripePaymentView, StripeSubscriptionWebhookView

urlpatterns = [
    path("create-payment/", CreateStripePaymentView.as_view(), name="create-payment"),
    path("stripe-webhook/", StripeSubscriptionWebhookView.as_view(), name="stripe-webhook"),
]
