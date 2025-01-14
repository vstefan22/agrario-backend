import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import PaymentTransaction
from subscriptions.models import PlatformSubscription
from reports.models import Report
from offers.models import Parcel
import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class CreateStripePaymentView(APIView):
    """
    Handles Stripe PaymentIntent creation for Analyse Plus and Subscription upgrades.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        payment_type = request.data.get("payment_type")
        amount = request.data.get("amount")
        currency = request.data.get("currency", "usd")
        metadata = request.data.get("metadata", {})

        if payment_type == "analyse_plus" and user.role != "landowner":
            raise PermissionDenied("Only landowners can purchase reports.")
        if payment_type == "subscription" and user.role != "developer":
            raise PermissionDenied("Only developers can upgrade subscriptions.")

        if payment_type == "analyse_plus":
            # Retrieve the report
            report_id = metadata.get("report_id")
            print("report_id", report_id)
            if not report_id:
                return Response({"error": "Report ID is required for Analyse Plus purchase."}, status=400)

            try:
                report = Report.objects.get(identifier=report_id)
                print("report", report)
            except Report.DoesNotExist:
                return Response({"error": "Invalid report ID."}, status=400)

            # Ensure the report is associated with the current user
            if not report.parcels.filter(created_by=user).exists():
                return Response({"error": "You are not authorized to purchase this report."}, status=403)

            # Set the amount based on the report
            analyse_plus_rate = getattr(settings, "ANALYSE_PLUS_RATE", 10)
            total_amount = sum(parcel.area_square_meters * analyse_plus_rate for parcel in report.parcels.all())

            metadata.update({"report_id": report_id})

        elif payment_type == "subscription":
            # Handle subscription upgrade
            plan_id = metadata.get("plan_id")
            if not plan_id:
                return Response({"error": "Plan ID is required for subscription."}, status=400)

            try:
                plan = PlatformSubscription.objects.get(id=plan_id)
            except PlatformSubscription.DoesNotExist:
                return Response({"error": "Invalid plan ID."}, status=400)

            total_amount = plan.amount_paid_per_month
            metadata.update({"plan_id": str(plan_id)})

            print("Metadata", metadata)

        try:
            # Create Stripe PaymentIntent
            intent = stripe.PaymentIntent.create(
                amount=int(total_amount * 100),
                currency=currency,
                metadata=metadata
            )

            # Record the transaction
            transaction = PaymentTransaction.objects.create(
                user=user,
                amount=total_amount,
                currency=currency,
                stripe_payment_intent=intent["id"],
                status="pending",
                payment_method="card"
            )
            print("Transaction", transaction)

            return Response({"client_secret": intent["client_secret"], "transaction_id": transaction.identifier}, status=200)
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e.user_message}")
            return Response({"error": e.user_message}, status=400)


class StripeWebhookView(APIView):
    """
    Handles Stripe webhook events for payment status updates.
    """
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_ENDPOINT_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError:
            return Response({"error": "Invalid payload."}, status=400)
        except stripe.error.SignatureVerificationError:
            return Response({"error": "Invalid signature."}, status=400)

        event_type = event.get("type")
        payment_intent = event["data"]["object"]
        stripe_payment_intent = payment_intent["id"]

        try:
            transaction = PaymentTransaction.objects.get(stripe_payment_intent=stripe_payment_intent)
            if event_type == "payment_intent.succeeded":
                transaction.status = "success"
                transaction.save()

                # Update the report visibility
                report_id = payment_intent["metadata"].get("report_id")
                if report_id:
                    try:
                        report = Report.objects.get(identifier=report_id)
                        report.visible_for = "USER"  # Grant access to the user
                        report.save()
                    except Report.DoesNotExist:
                        logger.error(f"Report with ID {report_id} not found.")
            elif event_type == "payment_intent.payment_failed":
                transaction.status = "failed"
                transaction.save()

        except PaymentTransaction.DoesNotExist:
            logger.error(f"PaymentTransaction with intent {stripe_payment_intent} not found.")

        return Response({"status": "success"}, status=200)