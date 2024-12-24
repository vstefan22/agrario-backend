"""Views for user management and authentication in the Marketplace application.

Includes views for user registration, login, email confirmation, and role-based dashboards.
"""

import logging
import stripe
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.utils.crypto import get_random_string
from django.utils.http import urlsafe_base64_decode
from django.utils.timezone import now, timedelta
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from offers.models import AreaOffer, Parcel

from .models import InviteLink, MarketUser, PaymentTransaction
from .serializers import UserRegistrationSerializer, UserSerializer

logger = logging.getLogger(__name__)

class MarketUserViewSet(viewsets.ModelViewSet): # pylint: disable=too-many-ancestors
    """
    ViewSet for managing MarketUser instances.
    """

    queryset = MarketUser.objects.all()
    serializer_class = UserRegistrationSerializer

    def get_permissions(self):
        """
        Set permissions based on the action being performed.
        """
        if self.action == "create":
            return [AllowAny()]
        return [IsAuthenticated()]

    @swagger_auto_schema(
        tags=["User Management"],
        operation_summary="Register a new user",
        operation_description="Create a new user by providing username, email, password, and role.",
        request_body=UserRegistrationSerializer,
        responses={
            201: openapi.Response("User registered successfully"),
            400: "Validation error",
        },
    )
    def create(self, request, *args, **kwargs):
        """
        Create a new user and send a confirmation email.
        """
        invite_code = request.data.get("invite_code")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        serializer.send_confirmation_email(user, invite_code=invite_code)

        return Response(
            {"message": "User registered successfully"}, status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(
        tags=["User Management"],
        operation_summary="Generate invite link",
        operation_description="Generate an invitation link for a user and send it via email.",
        responses={
            200: openapi.Response(
                description="Invite link generated successfully",
                examples={
                    "application/json": {
                        "invite_code": "unique_code",
                        "invitation_link": "http://localhost:8000/register?invite_code=unique_code",
                        "message": "Invite link generated and sent via email.",
                    }
                },
            )
        },
    )
    @action(detail=True, methods=["post"])
    def generate_invite_link(self, _request, _pk=None):
        """
        Generate an invitation link for the specified user.
        """
        user = self.get_object()
        invite_link, _ = InviteLink.objects.get_or_create(
            created_by=user, is_active=True
        )
        invitation_code = invite_link.uri_hash
        invitation_link = (
            f"http://localhost:8000/register?invite_code={invitation_code}"
        )

        send_mail(
            subject="Your Invitation Link",
            message=f"Hi {user.username},\n\nHere is your invite link:\n{invitation_link}",
            from_email="noreply@example.com",
            recipient_list=[user.email],
        )
        return Response(
            {
                "invite_code": invitation_code,
                "invitation_link": invitation_link,
                "message": "Invite link generated and sent via email.",
            },
            status=status.HTTP_200_OK,
        )
    
    @action(detail=False, methods=["post"])
    def handle_invite_link(self, request):
        """
        Check for an existing active invite link or create a new one.
        """
        user = request.user
        
        invite_link = InviteLink.objects.filter(created_by=user, is_active=True).first()
        
        if invite_link:
            invitation_code = invite_link.uri_hash
        else:
            invite_link = InviteLink.objects.create(created_by=user)
            invitation_code = invite_link.uri_hash

        invitation_link = f"http://127.0.0.1:8000/api/accounts/users/?invite_code={invitation_code}"

        return Response(
            {
                "invite_code": invitation_code,
                "invitation_link": invitation_link,
                "message": "Invite link generated or retrieved successfully.",
            },
            status=status.HTTP_200_OK,
        )

class ConfirmEmailView(APIView):
    """
    API view for confirming a user's email.
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=["User Management"],
        operation_summary="Confirm email",
        operation_description="Confirm a user's email using the provided token and uid.",
        responses={
            200: openapi.Response("Email confirmed successfully"),
            400: "Invalid or expired confirmation link",
        },
    )
    def get(self, request, uidb64, token):
        """
        Confirm a user's email based on the token and uid.
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
                {
                    "message": "Your account has been confirmed successfully. You can log in now."
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": "Invalid or expired confirmation link."},
            status=status.HTTP_400_BAD_REQUEST,
        )

class LoginView(APIView):
    """
    API view for user login.
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=["Authentication"],
        operation_summary="Log in a user",
        operation_description=(
            "Authenticate a user using email and password. "
            "Returns a token upon successful login."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING, description="User email"
                ),
                "password": openapi.Schema(
                    type=openapi.TYPE_STRING, description="User password"
                ),
            },
            required=["email", "password"],
        ),
        responses={
            200: openapi.Response(
                description="Successful login",
                examples={
                    "application/json": {
                        "token": "your_auth_token",
                        "user": {
                            "id": "uuid",
                            "username": "developer_user",
                            "email": "developer@example.com",
                        },
                    }
                },
            ),
            400: "Validation error",
            401: "Invalid credentials",
        },
    )
    def post(self, request):
        """
        Authenticate a user and return a token upon successful login.
        """
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.check_password(password):
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_email_confirmed:
            return Response(
                {"error": "Please confirm your email before logging in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        token, _ = Token.objects.get_or_create(user=user)
        user_data = UserSerializer(user).data
        return Response(
            {"token": token.key, "user": user_data}, status=status.HTTP_200_OK
        )


class RoleDashboardView(APIView):
    """
    API view for retrieving role-based dashboard data.
    """

    permission_classes = [IsAuthenticated]

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
        user = request.user

        if user.role == "landowner":
            try:
                parcels_count = Parcel.objects.filter(owner=user).count()
                offers_count = AreaOffer.objects.filter(
                    parcel__owner=user, is_active=True
                ).count()
            except Exception as e:
                logger.error("Error: %s", e)
                return Response(
                    {"error": "Failed to retrieve landowner data"},
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

        if user.role == "developer":
            try:
                watchlist_count = Parcel.objects.filter(
                    offers__parcel__owner=user
                ).count()
                auctions_count = AreaOffer.objects.filter(is_active=True).count()
            except Exception as e:
                logger.error("Error: %s", e)
                return Response(
                    {"error": "Failed to retrieve developer data"},
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

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve the profile of the authenticated user.
        """
        user_serializer = UserSerializer(request.user)
        return Response(user_serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        """
        Update the profile of the authenticated user.
        """
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    """
    Handle password reset requests.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Generate a reset code and send it to the user's email.
        """
        user = request.user
        reset_code = get_random_string(6, allowed_chars="0123456789")
        user.reset_code = reset_code
        user.reset_code_created_at = now()
        user.save()

        send_mail(
            "Password Reset Code",
            f"Your password reset code is: {reset_code}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
        return Response({"message": "Reset code sent."}, status=status.HTTP_200_OK)

    def get(self, request):
        """
        Return the reset code for the authenticated user if it exists.
        """
        user = request.user

        if not user.reset_code or now() - user.reset_code_created_at > timedelta(
            minutes=30
        ):
            return Response(
                {"error": "Reset code does not exist or has expired."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"reset_code": user.reset_code}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """
    Confirm password reset for a user.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Reset the user's password if the reset code matches.
        """
        user = request.user
        code = request.data.get("code")
        new_password = request.data.get("password")

        if not code or not new_password:
            return Response(
                {"error": "Code and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.reset_code != code:
            return Response(
                {"error": "Invalid reset code."}, status=status.HTTP_400_BAD_REQUEST
            )

        if now() - user.reset_code_created_at > timedelta(minutes=30):
            return Response(
                {"error": "Reset code expired."}, status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.reset_code = None
        user.reset_code_created_at = None
        user.save()

        return Response(
            {"message": "Password reset successful."}, status=status.HTTP_200_OK
        )
