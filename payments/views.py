import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import PaymentTransaction
from accounts.firebase_auth import verify_firebase_token
from .serializers import PaymentTransactionSerializer
from reports.models import Parcel
from reports.models import Report
from accounts.models import ProjectDeveloper
from subscriptions.models import PlatformSubscription, ProjectDeveloperSubscription
from django.utils import timezone
from offers.services import get_basket_summary

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
        try:
            # Explicitly fetch the ProjectDeveloper instance
            user = ProjectDeveloper.objects.get(pk=request.user.pk)
        except ProjectDeveloper.DoesNotExist:
            return Response({"error": "Only project developers can perform this action."}, status=403)

        parcel_ids = request.data.get("parcel_ids", [])  # List of parcel IDs (for Analyse Plus)
        plan_id = request.data.get("plan_id")  # Plan ID (for subscription upgrade)
        payment_method = request.data.get("payment_method", "card")  # Default to credit card
        currency = request.data.get("currency", "usd")  # Default to USD

        if payment_method == "sofort" and currency != "eur":
            return Response(
                {"error": "The 'sofort' payment method only supports EUR currency."},
                status=400,
            )

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

class StripeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        payment_type = request.data.get("payment_type")
        success_url = request.data.get("success_url", settings.STRIPE_SUCCESS_URL)
        cancel_url = request.data.get("cancel_url", settings.STRIPE_CANCEL_URL)
        
        if payment_type not in ["report", "subscription"]:
            raise ValidationError("Invalid payment type.")

        try:
            if payment_type == "report":
                basket_summary = get_basket_summary(user)
                if not basket_summary["parcel_ids"]:
                    raise ValidationError("Basket is empty.")
                
                amount = basket_summary["total_cost"]
                metadata = {"parcel_ids": ",".join(map(str, basket_summary["parcel_ids"]))}

            elif payment_type == "subscription":
                plan_id = request.data.get("plan_id")
                if not plan_id:
                    raise ValidationError("Plan ID is required for subscription.")
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
                            "currency": "usd",
                            "product_data": {
                                "name": "Purchase for {}".format(payment_type),
                            },
                            "unit_amount": int(amount * 100),
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
                amount=amount,
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
        
from rest_framework.views import APIView
from rest_framework.response import Response

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
