import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import PaymentTransaction
from subscriptions.models import PlatformSubscription

from offers.services import get_basket_summary
import logging
import json
from offers.models import BasketItem, Parcel
from accounts.models import ProjectDeveloper
from decimal import Decimal
import datetime
from subscriptions.models import ProjectDeveloperSubscription

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY
FRONTEND_URL = settings.FRONTEND_URL


class StripeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        payment_type = request.data.get("payment_type")

        if payment_type not in ["analyse_plus", "subscription"]:
            raise ValidationError("Invalid payment type.")

        try:
            if payment_type == "analyse_plus":
                success_url = f"{FRONTEND_URL}/landowner/my-plots/thank-you-order-request"
                cancel_url = f"{FRONTEND_URL}/landowner"
                basket_summary = get_basket_summary(user)
                subtotal_str = basket_summary["subtotal"].replace(",", "").strip()

                if not basket_summary["subtotal"]:
                    raise ValidationError("Basket is empty.")

                parcel_ids = BasketItem.objects.filter(
                    user=user).values_list('parcel_id', flat=True)

                metadata = {
                    "parcel_ids": ",".join(map(str, parcel_ids)),
                    "user_id": str(user.id),
                    "payment_type": payment_type
                }
                print("metadata: ", metadata)

            elif payment_type == "subscription":
                cancel_url = f"{FRONTEND_URL}/developer"
                success_url = f"{FRONTEND_URL}/developer/profile/subscribe"

                # Get tier by title instead of `id` if necessary
                plan_tier = request.data.get("plan_tier")  # Assume frontend sends "PREM", "ENTE", etc.
                print("plan_tier: ", plan_tier)
                if not plan_tier:
                    raise ValidationError("Plan Tier is required for subscription.")
                
                try:
                    plan = PlatformSubscription.objects.get(tier=plan_tier, valid_to="9999-01-01")
                    print("plan: ", plan)
                    subtotal_str = plan.amount_paid_per_month
                    metadata = {
                        "plan_tier": plan_tier,
                        "user_id": str(user.id),
                        "payment_type": payment_type,
                    }
                    print("metadata: ", metadata)
                except PlatformSubscription.DoesNotExist:
                    raise ValidationError("Invalid subscription plan.")

            # Create Stripe Session with payment_intent_data
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": "eur",
                        "product_data": {"name": f"Purchase for {payment_type}"},
                        "unit_amount": int(Decimal(subtotal_str) * 100),
                    },
                    "quantity": 1,
                }],
                metadata=metadata,  # Metadata for session
                payment_intent_data={  # Attach metadata to PaymentIntent
                    "metadata": metadata
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )
            print("session created: ", session)

            # Record Transaction
            PaymentTransaction.objects.create(
                user=user,
                amount=Decimal(subtotal_str),
                currency="EUR",
                stripe_payment_intent=session["id"],
                status="pending",
            )
            print("payment transaction created")

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
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            event = stripe.Event.construct_from(
                json.loads(payload), stripe.api_key
            )
            print("Webhook received event: ", json.dumps(event, indent=4))
        except ValueError:
            logger.error("Invalid payload")
            return Response({"error": "Invalid payload."}, status=400)

        event_type = event.get("type")
        print("Webhook event type: ", event_type)

        try:
            if event_type == "checkout.session.completed":
                session = event["data"]["object"]
                payment_intent_id = session.get("payment_intent")
                print("Session completed with payment_intent_id:", payment_intent_id)

                if payment_intent_id:
                    # Retrieve payment intent to access metadata
                    payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                    metadata = payment_intent.get("metadata", {})
                    print("Metadata from payment_intent:", metadata)

                    payment_type = metadata.get("payment_type")
                    print("Payment type:", payment_type)

                    # Handle 'analyse_plus' payment type
                    if payment_type == "analyse_plus":
                        parcel_ids = metadata.get("parcel_ids")
                        print("parcel_ids: ", parcel_ids)
                        if parcel_ids:
                            for parcel_id in parcel_ids.split(","):
                                parcel = Parcel.objects.filter(id=parcel_id)
                                if parcel.exists():
                                    parcel.update(analyse_plus=True)
                                    print("Parcel updated:", parcel)

                            BasketItem.objects.filter(parcel__id__in=parcel_ids.split(",")).delete()
                            print("Basket items deleted for parcel_ids:", parcel_ids)

                    # Handle 'subscription' payment type
                    elif payment_type == "subscription":
                        print("Subscription payment completed.")
                        user_id = metadata.get("user_id")
                        plan_tier = metadata.get("plan_tier")
                        print("Subscription metadata - User ID:", user_id, "Plan Tier:", plan_tier)

                        if user_id and plan_tier:
                            user = ProjectDeveloper.objects.get(identifier=user_id)
                            print("User found:", user)
                            plan = PlatformSubscription.objects.get(tier=plan_tier, valid_to="9999-01-01")
                            print("Plan found:", plan)

                            # Assign subscription to user
                            ProjectDeveloperSubscription.objects.create(
                                by_user=user,
                                tier=plan,
                                valid_from=datetime.date.today(),
                                billing_mode=ProjectDeveloperSubscription.BillingMode.MONTHLY,
                            )
                            print(f"Subscription '{plan_tier}' assigned to user ID {user_id}.")

                            user.tier = plan
                            user.save()  # Save the change to the database
                            print(f"User's tier updated to: {plan_tier}")

                    else:
                        print(f"Unhandled payment type: {payment_type}")

                    # Update transaction status
                    try:
                        transaction = PaymentTransaction.objects.get(
                            stripe_payment_intent=session["id"]
                        )
                        transaction.status = "success"
                        transaction.save()
                        logger.info(f"Transaction {transaction.id} marked as success.")
                    except PaymentTransaction.DoesNotExist:
                        logger.error(f"No transaction found for intent {payment_intent_id}")
                else:
                    logger.error("No payment_intent found in the session object.")

        except Exception as e:
            logger.error(f"Error handling webhook event: {str(e)}")
            return Response({"error": "Webhook handling failed."}, status=500)

        return Response({"status": "success"}, status=200)
