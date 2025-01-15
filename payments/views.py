import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import PaymentTransaction
from subscriptions.models import PlatformSubscription
from reports.models import Report
from offers.services import get_basket_summary
import logging
from offers.models import BasketItem
from decimal import Decimal

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        payment_type = request.data.get("payment_type")
        success_url = request.data.get(
            "success_url", settings.STRIPE_SUCCESS_URL)
        cancel_url = request.data.get("cancel_url", settings.STRIPE_CANCEL_URL)

        if payment_type not in ["report", "subscription"]:
            raise ValidationError("Invalid payment type.")

        try:
            if payment_type == "report":
                basket_summary = get_basket_summary(user)
                subtotal_str = basket_summary["subtotal"].replace(
                    ",", "").strip()
                if not basket_summary["subtotal"]:
                    raise ValidationError("Basket is empty.")

                amount = basket_summary["subtotal"]
                metadata = list(
                    BasketItem.objects.values_list('id', flat=True))

            elif payment_type == "subscription":
                plan_id = request.data.get("plan_id")
                if not plan_id:
                    raise ValidationError(
                        "Plan ID is required for subscription.")
                plan = PlatformSubscription.objects.get(id=plan_id)
                amount = plan.amount_paid_per_month
                metadata = {"plan_id": str(plan_id)}
            else:
                raise ValidationError("Unsupported payment type.")

            # Create Stripe Session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": "eur",
                            "product_data": {
                                "name": "Purchase for {}".format(payment_type),
                            },
                            "unit_amount": int(Decimal(subtotal_str) * 100),
                        },
                        "quantity": 1,
                    },
                ],
                metadata=metadata,
                success_url=success_url,
                cancel_url=cancel_url,
            )

            # Record Transaction
            PaymentTransaction.objects.create(
                user=user,
                amount=Decimal(subtotal_str),
                currency="USD",
                stripe_payment_intent=session.id,
                status="pending",
            )

            return Response({"session_url": session.url, "payment_intent": session.id}, status=200)

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e.user_message}")
            return Response({"error": e.user_message}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return Response({"error": str(e)}, status=500)


class StripeSuccessView(APIView):
    """
    Handle Stripe payment success.
    """

    def get(self, request):
        # You can redirect to a frontend or display a success message here
        return Response({"message": "Payment was successful. Thank you!"}, status=200)


class StripeCancelView(APIView):
    """
    Handle Stripe payment cancellation.
    """

    def get(self, request):
        # You can redirect to a frontend or display a cancellation message here
        return Response({"message": "Payment was cancelled. Please try again."}, status=200)


class StripeWebhookView(APIView):
    """
    Handles Stripe webhook events for payment status updates.
    """
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_ENDPOINT_SECRET

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret)
        except ValueError:
            return Response({"error": "Invalid payload."}, status=400)
        except stripe.error.SignatureVerificationError:
            return Response({"error": "Invalid signature."}, status=400)

        event_type = event.get("type")
        payment_intent = event["data"]["object"]
        stripe_payment_intent = payment_intent["id"]

        try:
            # Retrieve and update the transaction
            transaction = PaymentTransaction.objects.get(
                stripe_payment_intent=stripe_payment_intent)
            print("Transaction", transaction)
            if event_type == "payment_intent.succeeded":
                transaction.status = "success"
                print("Status before save:", transaction.status)
                transaction.save()
                print("Status after save:", transaction.status)

                # Update report visibility
                report_id = payment_intent["metadata"].get("report_id")
                if report_id:
                    report = Report.objects.filter(
                        identifier=report_id).first()
                    if report:
                        report.visible_for = "USER"  # Grant user access
                        report.save()

            elif event_type == "payment_intent.payment_failed":
                transaction.status = "failed"
                transaction.save()

        except PaymentTransaction.DoesNotExist:
            logger.error(f"Transaction with intent {
                         stripe_payment_intent} not found.")

        return Response({"status": "success"}, status=200)
