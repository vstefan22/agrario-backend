"""
Views for user management and authentication in the Marketplace application.

Includes views for user registration, login, email confirmation, and role-based dashboards.
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils.http import urlsafe_base64_decode
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import authenticate
import stripe
from .models import MarketUser, InviteLink, Landowner, ProjectDeveloper, PaymentTransaction
from .serializers import UserRegistrationSerializer, UserSerializer
from offers.models import Parcel, AreaOffer
from django.http import JsonResponse, HttpResponse
from django.conf import settings


class MarketUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing MarketUser instances.
    """
    queryset = MarketUser.objects.all()
    serializer_class = UserRegistrationSerializer

    def get_permissions(self):
        """
        Set permissions based on the action being performed.
        """
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    @swagger_auto_schema(
        tags=['User Management'],
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        serializer.send_confirmation_email(user)
        return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        tags=['User Management'],
        operation_summary="Generate invite link",
        operation_description="Generate an invitation link for a user and send it via email.",
        responses={
            200: openapi.Response(
                description="Invite link generated successfully",
                examples={
                    "application/json": {
                        "invite_code": "unique_code",
                        "invitation_link": "http://localhost:8000/register?invite_code=unique_code",
                        "message": "Invite link generated and sent via email."
                    }
                }
            )
        },
    )
    @action(detail=True, methods=['post'])
    def generate_invite_link(self, request, pk=None):
        """
        Generate an invitation link for the specified user.
        """
        user = self.get_object()
        invite_link, _ = InviteLink.objects.get_or_create(created_by=user, is_active=True)
        invitation_code = invite_link.uri_hash
        invitation_link = f"http://localhost:8000/register?invite_code={invitation_code}"

        send_mail(
            subject="Your Invitation Link",
            message=f"Hi {user.username},\n\nHere is your invite link:\n{invitation_link}",
            from_email="noreply@example.com",
            recipient_list=[user.email],
        )
        return Response({
            "invite_code": invitation_code,
            "invitation_link": invitation_link,
            "message": "Invite link generated and sent via email."
        }, status=status.HTTP_200_OK)


class ConfirmEmailView(APIView):
    """
    API view for confirming a user's email.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['User Management'],
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
            return Response({"error": "Invalid or expired confirmation link."}, status=status.HTTP_400_BAD_REQUEST)

        if default_token_generator.check_token(user, token):
            if user.is_email_confirmed:
                return Response({"message": "Your email is already confirmed. You can log in now."},
                                status=status.HTTP_200_OK)

            user.is_email_confirmed = True
            user.save()
            return Response({"message": "Your account has been confirmed successfully. You can log in now."},
                            status=status.HTTP_200_OK)

        return Response({"error": "Invalid or expired confirmation link."}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    API view for user login.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['Authentication'],
        operation_summary="Log in a user",
        operation_description="Authenticate a user using email and password. Returns a token upon successful login.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='User email'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='User password'),
            },
            required=['email', 'password'],
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
                            "email": "developer@example.com"
                        }
                    }
                }
            ),
            400: "Validation error",
            401: "Invalid credentials",
        },
    )
    def post(self, request):
        """
        Authenticate a user and return a token upon successful login.
        """
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_email_confirmed:
            return Response({'error': 'Please confirm your email before logging in.'}, status=status.HTTP_403_FORBIDDEN)

        token, _ = Token.objects.get_or_create(user=user)
        user_data = UserSerializer(user).data
        return Response({'token': token.key, 'user': user_data}, status=status.HTTP_200_OK)


class RoleDashboardView(APIView):
    """
    API view for retrieving role-based dashboard data.
    """
    permission_classes = [IsAuthenticated]


    @swagger_auto_schema(
        tags=['Dashboard'],
        operation_summary="Get dashboard",
        operation_description="Retrieve role-specific dashboard data based on the user's role.",
        responses={
            200: openapi.Response("Role-specific dashboard data"),
            400: "Invalid or missing role",
        },
    )


    def get(self, request):

        # Check if user is authenticated
        if not request.user.is_authenticated:
            print("Authentication failed: User not authenticated")
            return Response({"error": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

        user = request.user

        # Check if the user role is 'landowner'
        if user.role == 'landowner':
            try:
                parcels_count = Parcel.objects.filter(owner=user).count()
                offers_count = AreaOffer.objects.filter(parcel__owner=user, is_active=True).count()
                print(f"Landowner Dashboard - Parcels Owned: {parcels_count}, Active Offers: {offers_count}")
            except Exception as e:
                print(f"Error while fetching Landowner data: {e}")
                return Response({"error": "Failed to retrieve landowner data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({
                "dashboard_greeting": f"Welcome Landowner {user.username}!",
                "parcels_owned": parcels_count,
                "active_offers": offers_count,
                "quick_links": [
                    {"name": "Manage Parcels", "url": "/parcels"},
                    {"name": "Place Offers", "url": "/offers"},
                    {"name": "Analysis & Reports", "url": "/analysis"},
                ],
                "notifications": "You have 2 new messages."
            })

        # Check if the user role is 'developer'
        if user.role == 'developer':
            try:
                watchlist_count = Parcel.objects.filter(offers__parcel__owner=user).count()
                auctions_count = AreaOffer.objects.filter(is_active=True).count()
                print(f"Developer Dashboard - Watchlist Items: {watchlist_count}, Active Auctions: {auctions_count}")
            except Exception as e:
                print(f"Error while fetching Developer data: {e}")
                return Response({"error": "Failed to retrieve developer data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({
                "dashboard_greeting": f"Welcome Developer {user.username}!",
                "watchlist_items": watchlist_count,
                "active_auctions": auctions_count,
                "quick_links": [
                    {"name": "Search Parcels", "url": "/search"},
                    {"name": "Manage Profile", "url": "/profile"},
                    {"name": "Subscriptions", "url": "/subscriptions"},
                ],
                "notifications": "You have 1 new bid update."
            })

        # Role not assigned or invalid
        print("Error: Role not assigned or invalid")
        return Response({"error": "Role not assigned or invalid"}, status=status.HTTP_400_BAD_REQUEST)
    


# stripe
# Set your Stripe secret key
stripe.api_key = settings.STRIPE_SECRET_KEY

def stripe_webhook(request):
    """
    Handle Stripe webhook events for payment verification.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    endpoint_secret = settings.STRIPE_ENDPOINT_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponse(status=400)  # Invalid payload
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)  # Invalid signature

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_successful_payment(payment_intent)
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        handle_failed_payment(payment_intent)

    return JsonResponse({'status': 'success'})

def handle_successful_payment(payment_intent):
    """
    Handle successful payment events.
    """
    transaction_id = payment_intent['id']
    amount_received = payment_intent['amount_received'] / 100  # Convert cents to dollars
    customer_email = payment_intent['charges']['data'][0]['billing_details']['email']

    # Create or update the payment transaction
    PaymentTransaction.objects.update_or_create(
        transaction_id=transaction_id,
        defaults={
            'status': 'completed',
            'amount': amount_received,
            'email': customer_email,
        }
    )

def handle_failed_payment(payment_intent):
    """
    Handle failed payment events.
    """
    transaction_id = payment_intent['id']

    # Update the payment transaction status to failed
    PaymentTransaction.objects.filter(transaction_id=transaction_id).update(status='failed')
