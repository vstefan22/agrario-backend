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
        Create a Stripe payment session for Analyse Plus and update parcel status.
        """
        user = request.user
        parcel_id = request.data.get("parcel_id")
        amount = request.data.get("amount", 100)  # Default: $100 for testing
        currency = request.data.get("currency", "usd")

        if not parcel_id:
            return Response({"error": "Parcel ID is required."}, status=400)

        try:
            # Create a Stripe Payment Intent
            intent = stripe.PaymentIntent.create(
                amount=int(float(amount) * 100),  # Convert to cents
                currency=currency,
                metadata={"user_id": user.id, "parcel_id": parcel_id},  # Include parcel info
            )

            # Record the transaction
            transaction = PaymentTransaction.objects.create(
                user=user,
                amount=amount,
                currency=currency,
                stripe_payment_intent=intent["id"],
                status="success",  # Set as success since this is test-only
            )

            # Update parcel status
            try:
                parcel = Parcel.objects.get(id=parcel_id)
                parcel.status = "purchased"  # Update the status
                parcel.save()  # Save the changes
            except Parcel.DoesNotExist:
                return Response({"error": "Parcel does not exist."}, status=404)

            return Response({
                "client_secret": intent["client_secret"],
                "transaction_id": transaction.identifier,
                "message": f"Parcel {parcel_id} marked as purchased.",
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
        except ValueError:
            return Response({"error": "Invalid payload."}, status=400)
        except stripe.error.SignatureVerificationError:
            return Response({"error": "Invalid signature."}, status=400)

        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            transaction_id = intent["id"]
            metadata = intent.get("metadata", {})
            print("metadata: ", metadata)
            parcel_id = metadata.get("parcel_id")

            # Update transaction status
            PaymentTransaction.objects.filter(
                stripe_payment_intent=transaction_id
            ).update(status="success")

            # Mark the parcel as purchased
            if parcel_id:
                try:
                    parcel = Parcel.objects.get(id=parcel_id)
                    parcel["status"] = "purchased"
                    parcel.save()
                except Parcel.DoesNotExist:
                    pass

        elif event["type"] == "payment_intent.payment_failed":
            intent = event["data"]["object"]
            transaction_id = intent["id"]
            PaymentTransaction.objects.filter(
                stripe_payment_intent=transaction_id
            ).update(status="failed")

        return Response({"status": "success"})