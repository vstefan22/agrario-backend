from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import MarketUser, InviteLink
from .serializers import UserRegistrationSerializer, UserSerializer
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_decode
from rest_framework.views import APIView
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import authenticate, login
from rest_framework.authtoken.models import Token
from .models import Landowner, ProjectDeveloper
from offers.models import Parcel, AreaOffer

class MarketUserViewSet(viewsets.ModelViewSet):
    queryset = MarketUser.objects.all()
    serializer_class = UserRegistrationSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]  # Default for other actions

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
        user = self.get_object()
        invite_link, created = InviteLink.objects.get_or_create(created_by=user, is_active=True)
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
    permission_classes = [AllowAny]  # Allow anyone to access this endpoint

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

        try:
            token, _ = Token.objects.get_or_create(user=user)
        except Exception as e:
            return Response({'error': f'Failed to create token: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        user_data = UserSerializer(user).data
        return Response({'token': token.key, 'user': user_data}, status=status.HTTP_200_OK)


class RoleDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['Dashboard'],
        operation_summary="Get dashboard",
        operation_description="Retrieve role-specific dashboard data based on whether the user is a landowner or developer.",
        responses={
            200: openapi.Response(
                description="Role-specific dashboard",
                examples={
                    "application/json": {
                        "dashboard_greeting": "Welcome Landowner user!",
                        "parcels_owned": 3,
                        "active_offers": 2,
                        "quick_links": [
                            {"name": "Manage Parcels", "url": "/parcels"},
                            {"name": "Place Offers", "url": "/offers"},
                            {"name": "Analysis & Reports", "url": "/analysis"}
                        ],
                        "notifications": "You have 2 new messages."
                    }
                }
            ),
            400: "Role not assigned or invalid",
        },
    )
    def get(self, request):
        user = request.user
        if user.role == 'landowner':
            parcels = Parcel.objects.filter(owner=user).count()
            active_offers = AreaOffer.objects.filter(parcel__owner=user, is_active=True).count()
            return Response({
                "dashboard_greeting": f"Welcome Landowner {user.username}!",
                "parcels_owned": parcels,
                "active_offers": active_offers,
                "quick_links": [
                    {"name": "Manage Parcels", "url": "/parcels"},
                    {"name": "Place Offers", "url": "/offers"},
                    {"name": "Analysis & Reports", "url": "/analysis"},
                ],
                "notifications": "You have 2 new messages."
            })

        elif user.role == 'developer':
            watchlist_items = Parcel.objects.filter(offers__parcel__owner=user).count()
            active_auctions = AreaOffer.objects.filter(is_active=True).count()
            return Response({
                "dashboard_greeting": f"Welcome Developer {user.username}!",
                "watchlist_items": watchlist_items,
                "active_auctions": active_auctions,
                "quick_links": [
                    {"name": "Search Parcels", "url": "/search"},
                    {"name": "Manage Profile", "url": "/profile"},
                    {"name": "Subscriptions", "url": "/subscriptions"},
                ],
                "notifications": "You have 1 new bid update."
            })
        return Response({"error": "Role not assigned or invalid"}, status=400)
