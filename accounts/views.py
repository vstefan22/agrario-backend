"""Views for user management and authentication in the Marketplace application.

Includes views for user registration, login, email confirmation, and role-based dashboards.
"""

import logging, requests
import stripe
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.utils.crypto import get_random_string
from django.utils.http import urlsafe_base64_decode
from django.utils.timezone import now, timedelta
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView
from offers.models import AreaOffer, Parcel
from .models import InviteLink, MarketUser, PaymentTransaction
from .firebase_auth import FirebaseAuthentication, verify_firebase_token, create_firebase_user
from .models import MarketUser
from .serializers import UserRegistrationSerializer, UserSerializer
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from firebase_admin import auth as firebase_auth

logger = logging.getLogger(__name__)

class MarketUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing MarketUser instances.
    """
    queryset = MarketUser.objects.all()
    serializer_class = UserRegistrationSerializer

    def get_permissions(self):
        # Allow unauthenticated access to the 'confirm_email' action
        if self.action == "create" or self.action == "confirm_email":
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """
        Handles user registration, Firebase user creation, and email confirmation.
        """
        invite_code = request.data.get("invite_code")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create Firebase user
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        firebase_user = create_firebase_user(email=email, password=password)

        # Create local user
        user = serializer.save()
        user.firebase_uid = firebase_user.uid
        user.is_active = False
        user.save()

        # Send confirmation email
        self.send_confirmation_email(user)

        return Response(
            {"message": "User registered successfully. Please confirm your email."},
            status=status.HTTP_201_CREATED,
        )

    def send_confirmation_email(self, user):
        """
        Generate and send an email confirmation link.
        """
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        confirmation_link = f"{settings.BACKEND_URL}/api/accounts/users/confirm-email/{uid}/{token}/"
        send_mail(
            subject="Confirm Your Email Address",
            message=f"Hi {user.username},\n\nClick the link below to confirm your email:\n{confirmation_link}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="confirm-email/(?P<uidb64>[^/.]+)/(?P<token>[^/.]+)",
    )
    def confirm_email(self, request, uidb64, token):
        """
        Confirms the user's email address.
        """
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = MarketUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, MarketUser.DoesNotExist):
            return Response(
                {"error": "Invalid or expired confirmation link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if default_token_generator.check_token(user, token):
            if user.is_email_confirmed:
                return Response(
                    {"message": "Your email is already confirmed. You can log in now."},
                    status=status.HTTP_200_OK,
                )
            user.is_email_confirmed = True
            user.is_active = True
            user.save()

            invite_code = request.GET.get("invite_code")
            if invite_code:
                try:
                    invite_link = InviteLink.objects.get(uri_hash=invite_code, is_active=True)
                    invite_link.successful_referrals += 1
                    invite_link.save()
                except InviteLink.DoesNotExist:
                    return Response(
                        {"error": "Invalid invite code."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            return Response(
                {"message": "Your account has been confirmed successfully. You can log in now."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": "Invalid or expired confirmation link."},
            status=status.HTTP_400_BAD_REQUEST,
        )

class LoginView(APIView):
    """
    Handles user login and returns a Firebase token upon successful authentication.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # Validate input
        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Authenticate user using Firebase
        try:
            user_record = firebase_auth.get_user_by_email(email)
        except firebase_auth.UserNotFoundError:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            return Response(
                {"error": f"Firebase authentication error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Verify the password using Firebase's REST API
        try:
            firebase_token = self.verify_firebase_password(email, password)
        except AuthenticationFailed as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            return Response(
                {"error": f"Error verifying password: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Retrieve the user from the database
        try:
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response(
                {"error": "User not found in the system."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if the email is confirmed
        if not user.is_email_confirmed:
            return Response(
                {"error": "Please confirm your email address before logging in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Return the Firebase token and user details
        return Response(
            {
                "message": "Login successful",
                "user": {
                    "email": user.email,
                    "firebase_uid": user_record.uid,
                },
                "firebase_token": firebase_token,
            },
            status=status.HTTP_200_OK,
        )

    def verify_firebase_password(self, email, password):
        """
        Verifies the provided email and password using Firebase's REST API.

        Args:
            email (str): The user's email address.
            password (str): The user's password.

        Returns:
            str: A Firebase ID token if authentication is successful.

        Raises:
            AuthenticationFailed: If the email or password is incorrect.
        """
        import requests

        firebase_api_key = settings.FIREBASE_API_KEY
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True,
        }

        response = requests.post(url, json=payload)
        if response.status_code != 200:
            raise AuthenticationFailed("Invalid email or password.")

        data = response.json()
        return data["idToken"]

class RoleDashboardView(APIView):
    """
    API view for retrieving role-based dashboard data.
    """

    permission_classes = [AllowAny]  # Explicitly allow unauthenticated access for token verification

    @swagger_auto_schema(
        tags=["Dashboard"],
        operation_summary="Get dashboard",
        operation_description="Retrieve role-specific dashboard data based on the user's role.",
        responses={
            200: openapi.Response("Role-specific dashboard data"),
            400: "Invalid or missing role",
        },
    )
    def get(self, request):
        """
        Retrieve dashboard data based on the user's role.
        """
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response({"error": "Authentication token not provided."}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split("Bearer ")[1]

        # Verify Firebase token
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            return Response({"error": "Invalid or expired Firebase token."}, status=status.HTTP_401_UNAUTHORIZED)

        # Check if user exists in the database
        email = decoded_token.get("email")
        if not email:
            return Response({"error": "Email not found in token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user is active
        if not user.is_active:
            return Response({"error": "User account is inactive."}, status=status.HTTP_403_FORBIDDEN)

        # Fetch dashboard data based on the user's role
        if user.role == "landowner":
            try:
                # Replace 'owner' with the actual field name from the Parcel model
                parcels_count = Parcel.objects.filter(created_by=user).count()
                offers_count = AreaOffer.objects.filter(
                    parcel__created_by=user, is_active=True
                ).count()
            except Exception as e:
                logger.error(f"Error retrieving landowner data: {e}")
                return Response(
                    {"error": "Failed to retrieve landowner data."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "dashboard_greeting": f"Welcome Landowner {user.username}!",
                    "parcels_owned": parcels_count,
                    "active_offers": offers_count,
                    "quick_links": [
                        {"name": "Manage Parcels", "url": "/parcels"},
                        {"name": "Place Offers", "url": "/offers"},
                        {"name": "Analysis & Reports", "url": "/analysis"},
                    ],
                    "notifications": "You have 2 new messages.",
                },
                status=status.HTTP_200_OK,
            )

        elif user.role == "developer":
            try:
                watchlist_count = Parcel.objects.filter(offers__parcel__owner=user).count()
                auctions_count = AreaOffer.objects.filter(is_active=True).count()
            except Exception as e:
                logger.error("Error retrieving developer data: %s", e)
                return Response(
                    {"error": "Failed to retrieve developer data."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "dashboard_greeting": f"Welcome Developer {user.username}!",
                    "watchlist_items": watchlist_count,
                    "active_auctions": auctions_count,
                    "quick_links": [
                        {"name": "Search Parcels", "url": "/search"},
                        {"name": "Manage Profile", "url": "/profile"},
                        {"name": "Subscriptions", "url": "/subscriptions"},
                    ],
                    "notifications": "You have 1 new bid update.",
                },
                status=status.HTTP_200_OK,
            )

        # If the user's role is not assigned or invalid
        return Response(
            {"error": "Role not assigned or invalid."},
            status=status.HTTP_400_BAD_REQUEST,
        )

stripe.api_key = settings.STRIPE_SECRET_KEY


def stripe_webhook(request):
    """
    Handle Stripe webhook events for payment verification.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = settings.STRIPE_ENDPOINT_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        handle_successful_payment(payment_intent)
    elif event["type"] == "payment_intent.payment_failed":
        payment_intent = event["data"]["object"]
        handle_failed_payment(payment_intent)

    return JsonResponse({"status": "success"})


def handle_successful_payment(payment_intent):
    """
    Handle successful payment events.
    """
    transaction_id = payment_intent["id"]
    amount_received = payment_intent["amount_received"] / 100
    customer_email = payment_intent["charges"]["data"][0]["billing_details"]["email"]

    PaymentTransaction.objects.update_or_create(
        transaction_id=transaction_id,
        defaults={
            "status": "completed",
            "amount": amount_received,
            "email": customer_email,
        },
    )


def handle_failed_payment(payment_intent):
    """
    Handle failed payment events.
    """
    transaction_id = payment_intent["id"]
    PaymentTransaction.objects.filter(transaction_id=transaction_id).update(
        status="failed"
    )


class MarketUserProfileView(APIView):
    """
    View to retrieve or update the profile of the authenticated user.
    """

    permission_classes = [AllowAny]  # Allow access for Firebase token validation

    def get(self, request):
        """
        Retrieve the profile of the authenticated user.
        """
        # Verify Firebase token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response({"error": "Authentication token not provided."}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            return Response({"error": "Invalid or expired Firebase token."}, status=status.HTTP_401_UNAUTHORIZED)

        # Retrieve user based on email
        email = decoded_token.get("email")
        if not email:
            return Response({"error": "Email not found in token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Serialize user data
        user_serializer = UserSerializer(user)
        return Response(user_serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        """
        Update the profile of the authenticated user.
        """
        # Same Firebase token validation as in the GET method
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response({"error": "Authentication token not provided."}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            return Response({"error": "Invalid or expired Firebase token."}, status=status.HTTP_401_UNAUTHORIZED)

        email = decoded_token.get("email")
        try:
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Update user data
        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class FirebasePasswordResetRequestView(APIView):
    """
    View to handle password reset requests via Firebase.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """
        Sends a password reset email to the user using Firebase.
        """
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        firebase_api_key = settings.FIREBASE_API_KEY
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={firebase_api_key}"

        payload = {
            "requestType": "PASSWORD_RESET",
            "email": email
        }

        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return Response({"message": "Password reset email sent successfully."}, status=status.HTTP_200_OK)

        return Response(
            {"error": "Failed to send password reset email. Please check the email address."},
            status=status.HTTP_400_BAD_REQUEST,
        )
