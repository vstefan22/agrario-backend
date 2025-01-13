from django.urls import path
from .views import CreateStripePaymentView, StripeSessionView, StripeSuccessView, StripeCancelView

urlpatterns = [
    path("create-payment/", CreateStripePaymentView.as_view(), name="create-payment"),
    path("create-stripe-session/", StripeSessionView.as_view(), name="stripe-webhook"),
    path("success/", StripeSuccessView.as_view(), name="stripe-success"),
    path("cancel/", StripeCancelView.as_view(), name="stripe-cancel"),
]
