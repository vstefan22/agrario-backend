import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from .models import PaymentTransaction
from accounts.firebase_auth import verify_firebase_token
from .serializers import PaymentTransactionSerializer
from reports.models import Parcel
from reports.models import Report

stripe.api_key = settings.STRIPE_SECRET_KEY

class FirebaseIsAuthenticated(BasePermission):
    """
    Custom permission class for Firebase authentication.
    """
    def has_permission(self, request, view):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            request.error_message = {"error": "Authentication header or Bearer token is missing."}
            return False

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            request.error_message = {"error": "Invalid or expired Firebase token."}
            return False

        request.user_email = decoded_token.get("email")
        request.user_role = decoded_token.get("role", "user")
        return True

class CreateStripePaymentView(APIView):
    permission_classes = [FirebaseIsAuthenticated]

    def post(self, request):
        """
        Create a Stripe payment session for Analyse Plus.
        """
        user = request.user
        parcel_ids = request.data.get("parcel_ids", [])  # List of parcel IDs
        payment_method = request.data.get("payment_method", "card")  # Default to credit card
        currency = request.data.get("currency", "usd")  # Default to USD

        if not parcel_ids:
            return Response({"error": "Parcel IDs are required."}, status=400)

        # Fetch parcels
        parcels = Parcel.objects.filter(id__in=parcel_ids, created_by=user)
        if not parcels.exists():
            return Response({"error": "No valid parcels found."}, status=400)

        # Calculate total amount
        analyse_plus_rate = getattr(settings, "ANALYSE_PLUS_RATE", 10)  # Default to 10 if not set
        total_amount = sum(parcel.area_square_meters * analyse_plus_rate for parcel in parcels)

        print("Total amount:", total_amount)
        print("Analyse Plus rate:", analyse_plus_rate)
        print("Parcels:", parcels)
        print("pracel in parcels")
        for parcel in parcels:
            print(parcel.area_square_meters, parcel.area_square_meters * analyse_plus_rate)

        # Check Stripe's minimum charge amount for the currency
        minimum_amount = 50  # Example: Stripe's minimum charge for USD is 50 cents
        if currency.lower() == "usd":
            minimum_amount = 50
        elif currency.lower() == "eur":
            minimum_amount = 50

        if total_amount * 100 < minimum_amount:  # Stripe expects amounts in cents
            return Response(
                {
                    "error": f"The total amount must be at least {minimum_amount / 100:.2f} {currency.upper()}."
                },
                status=400,
            )

        try:
            # Create a Stripe Payment Intent
            intent = stripe.PaymentIntent.create(
                amount=int(total_amount * 100),  # Stripe expects amounts in cents
                currency=currency,
                payment_method_types=["card", "sofort", "paypal"],  # Support multiple payment methods
                metadata={"user_id": user.id, "parcel_ids": ",".join(map(str, parcel_ids))},
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
        except Exception as e:
            return Response({"error": str(e)}, status=500)



class StripeWebhookView(APIView):
    """
    Handle Stripe webhooks for payment updates.
    """
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_ENDPOINT_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response({"error": "Invalid payload or signature."}, status=400)

        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            transaction_id = intent["id"]
            metadata = intent.get("metadata", {})
            parcel_ids = metadata.get("parcel_ids", "").split(",")

            # Update transaction status
            PaymentTransaction.objects.filter(stripe_payment_intent=transaction_id).update(status="success")

            # Update parcels
            for parcel_id in parcel_ids:
                try:
                    parcel = Parcel.objects.get(id=parcel_id)
                    parcel.status = "purchased"
                    parcel.save()
                except Parcel.DoesNotExist:
                    continue

        elif event["type"] == "payment_intent.payment_failed":
            intent = event["data"]["object"]
            transaction_id = intent["id"]
            PaymentTransaction.objects.filter(stripe_payment_intent=transaction_id).update(status="failed")

        return Response({"status": "success"})