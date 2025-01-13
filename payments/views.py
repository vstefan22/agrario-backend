import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.exceptions import PermissionDenied
from .models import PaymentTransaction
from accounts.firebase_auth import verify_firebase_token
from .serializers import PaymentTransactionSerializer
from reports.models import Parcel
from reports.models import Report
from accounts.models import ProjectDeveloper
from subscriptions.models import PlatformSubscription, ProjectDeveloperSubscription
from django.utils import timezone

import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

class FirebaseIsAuthenticated(BasePermission):
    """
    Custom permission class for Firebase authentication.
    """

    def has_permission(self, request, view):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise PermissionDenied("Authentication token is missing or invalid.")

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            raise PermissionDenied("Invalid or expired Firebase token.")

        # Attach decoded token data to request
        request.user_email = decoded_token.get("email")
        request.user_role = decoded_token.get("role", "user")
        return True

class CreateStripePaymentView(APIView):
    permission_classes = [FirebaseIsAuthenticated]

    def post(self, request):
        """
        Create a Stripe payment session for Analyse Plus or Subscription Upgrade.
        """
        user = request.user
        parcel_ids = request.data.get("parcel_ids", [])  # List of parcel IDs (for Analyse Plus)
        plan_id = request.data.get("plan_id")  # Plan ID (for subscription upgrade)
        payment_method = request.data.get("payment_method", "card")  # Default to credit card
        currency = request.data.get("currency", "usd")  # Default to USD

        # Determine the payment type: Analyse Plus or Subscription Upgrade
        if plan_id:
            # Handle Subscription Upgrade
            try:
                subscription_plan = PlatformSubscription.objects.get(id=plan_id)
            except PlatformSubscription.DoesNotExist:
                return Response({"error": "Invalid plan ID."}, status=400)

            # Prevent duplicate subscription to the same plan
            if user.tier == subscription_plan:
                return Response({"error": "You are already subscribed to this plan."}, status=400)

            total_amount = subscription_plan.amount_paid_per_month
            metadata = {"user_id": user.id, "plan_id": plan_id}
        elif parcel_ids:
            # Handle Analyse Plus
            parcels = Parcel.objects.filter(id__in=parcel_ids, created_by=user)
            if not parcels.exists():
                return Response({"error": "No valid parcels found."}, status=400)

            analyse_plus_rate = getattr(settings, "ANALYSE_PLUS_RATE", 10)  # Default to 10 if not set
            total_amount = sum(parcel.area_square_meters * analyse_plus_rate for parcel in parcels)
            metadata = {"user_id": user.id, "parcel_ids": ",".join(map(str, parcel_ids))}
        else:
            return Response({"error": "Either parcel IDs or a plan ID is required."}, status=400)

        # Validate minimum charge dynamically
        minimum_amount = self.get_minimum_charge(currency)
        if minimum_amount is None:
            return Response({"error": f"Unsupported currency: {currency}"}, status=400)
        if total_amount * 100 < minimum_amount:  # Stripe expects amounts in cents
            return Response(
                {"error": f"The total amount must be at least {minimum_amount / 100:.2f} {currency.upper()}."},
                status=400,
            )

        try:
            # Create a Stripe Payment Intent
            intent = stripe.PaymentIntent.create(
                amount=int(total_amount * 100),  # Stripe expects amounts in cents
                currency=currency,
                payment_method_types=["card", "sofort", "paypal"],  # Support multiple payment methods
                metadata=metadata,
            )

            # Record the transaction
            transaction = PaymentTransaction.objects.create(
                user=user,
                amount=total_amount,
                currency=currency,
                stripe_payment_intent=intent["id"],
                payment_method=payment_method,
                status="pending",
            )

            return Response({
                "client_secret": intent["client_secret"],
                "transaction_id": transaction.identifier,
                "message": "Payment intent created successfully.",
            }, status=200)
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e.user_message}", exc_info=True)
            return Response({"error": e.user_message}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return Response({"error": "An unexpected error occurred. Please try again."}, status=500)

    @staticmethod
    def get_minimum_charge(currency):
        """
        Retrieves the minimum charge for the specified currency from Stripe's documentation or API.
        Fallback to a default value if the currency is unsupported.
        """
        minimum_amounts = {
            "usd": 50,  # in cents
            "eur": 50,  # in cents
            # Add other currencies if required
        }
        return minimum_amounts.get(currency.lower(), None)

class StripeSubscriptionWebhookView(APIView):
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_ENDPOINT_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            return Response({"error": str(e)}, status=400)

        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            metadata = intent.get("metadata", {})
            user_id = metadata.get("user_id")
            plan_id = metadata.get("plan_id")

            # Update subscription
            user = ProjectDeveloper.objects.get(id=user_id)
            plan = PlatformSubscription.objects.get(id=plan_id)
            ProjectDeveloperSubscription.objects.create(
                by_user=user,
                tier=plan,
                valid_from=timezone.now(),
            )

            try:
                user = ProjectDeveloper.objects.get(id=user_id)
                plan = PlatformSubscription.objects.get(id=plan_id)

                # Upgrade user privileges
                user.upgrade_privileges(plan)

                # Log success
                logger.info(f"User {user.email} upgraded to plan {plan.title}")
            except Exception as e:
                logger.error(f"Error upgrading privileges: {e}", exc_info=True)

        elif event["type"] == "payment_intent.payment_failed":
            intent = event["data"]["object"]
            logger.error(f"Payment failed for intent: {intent['id']}")

        return Response({"status": "success"})