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
from .models import MarketUser
from .firebase_auth import FirebaseAuthentication, verify_firebase_token, create_firebase_user
from .serializers import UserRegistrationSerializer, UserSerializer, LandownerProfileSerializer, DeveloperProfileSerializer
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from firebase_admin import auth as firebase_auth
from google.cloud import storage
from .utils import get_user_role

logger = logging.getLogger(__name__)

class MarketUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing MarketUser instances.
    """
    queryset = MarketUser.objects.all()
    serializer_class = UserRegistrationSerializer

    def get_permissions(self):
        """
        Custom permissions for create and confirm_email actions.
        """
        if self.action in ["create", "confirm_email"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    @swagger_auto_schema(
        operation_summary="Create a new user",
        operation_description="Handles user registration, Firebase user creation, and email confirmation.",
        request_body=UserRegistrationSerializer,
        responses={
            201: openapi.Response("User registered successfully. Please confirm your email."),
            400: "Bad Request - Validation Error",
        },
    )
    def create(self, request, *args, **kwargs):
        """
        Handles user registration, Firebase user creation, and email confirmation.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extract validated data
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        role = serializer.validated_data["role"]

        # Create Firebase user
        firebase_user = create_firebase_user(email=email, password=password)

        # Create local user
        user = serializer.save()
        user.firebase_uid = firebase_user.uid
        user.is_active = False  # Inactive until email is confirmed
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
            message=f"Hi {user.first_name},\n\nClick the link below to confirm your email:\n{confirmation_link}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
        )

    @swagger_auto_schema(
        operation_summary="Confirm email address",
        operation_description="Confirms the user's email address using a token and UID.",
        manual_parameters=[
            openapi.Parameter(
                "uidb64",
                openapi.IN_PATH,
                description="Base64 encoded user ID",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "token",
                openapi.IN_PATH,
                description="Token for email confirmation",
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={
            200: openapi.Response("Email confirmed successfully."),
            400: "Invalid or expired confirmation link.",
        },
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
            user.privacy_accepted = True
            user.terms_accepted = True
            user.save()
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

    @swagger_auto_schema(
        operation_summary="User Login",
        operation_description=(
            "Authenticates a user using their email and password. "
            "If successful, returns a Firebase token and user details."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description="The email address of the user"
                ),
                "password": openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description="The password of the user"
                ),
            },
            required=["email", "password"],
        ),
        responses={
            200: openapi.Response(
                description="Login successful",
                examples={
                    "application/json": {
                        "message": "Login successful",
                        "user": {
                            "email": "example@example.com",
                            "firebase_uid": "12345abcdef",
                        },
                        "firebase_token": "eyJhbGciOiJIUzI1NiIsInR..."
                    }
                },
            ),
            400: openapi.Response(
                description="Bad Request - Missing or invalid input",
                examples={
                    "application/json": {"error": "Email and password are required."}
                },
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid email or password",
                examples={
                    "application/json": {"error": "Invalid email or password."}
                },
            ),
            403: openapi.Response(
                description="Forbidden - Email not confirmed",
                examples={
                    "application/json": {
                        "error": "Please confirm your email address before logging in."
                    }
                },
            ),
            404: openapi.Response(
                description="Not Found - User does not exist",
                examples={
                    "application/json": {"error": "User not found in the system."}
                },
            ),
            500: openapi.Response(
                description="Internal Server Error",
                examples={
                    "application/json": {
                        "error": "Firebase authentication error: An unexpected error occurred."
                    }
                },
            ),
        },
    )
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
                    "db_uid": user.id
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

    permission_classes = [AllowAny]

    def get_tutorial_links(self, role):
        """
        Retrieves public links to tutorial videos based on the user's role.
        """
        try:
            storage_client = storage.Client.from_service_account_json(settings.GOOGLE_APPLICATION_CREDENTIALS)
            bucket = storage_client.bucket(settings.G_CLOUD_BUCKET_NAME_STATIC)

            # Use the configurable prefix
            prefix = settings.TUTORIAL_LINK_PREFIX.format(role=role)
            logger.info(f"Fetching files from bucket with prefix: {prefix}")

            blobs = bucket.list_blobs(prefix=prefix)
            tutorial_links = []

            for blob in blobs:
                logger.info(f"Found blob: {blob.name}")
                if not blob.name.endswith("/"):  # Ignore directories
                    tutorial_links.append(blob.public_url)

            if not tutorial_links:
                logger.warning(f"No tutorials found for role: {role}")
            return tutorial_links
        except Exception as e:
            logger.error(f"Error retrieving tutorial links for role '{role}': {e}")
            return []

    @swagger_auto_schema(
        tags=["Dashboard"],
        operation_summary="Get Dashboard",
        operation_description=(
            "Retrieve role-specific dashboard data along with tutorial links. "
            "The user's role determines the content of the dashboard. "
            "Includes a list of tutorial videos hosted on Google Cloud Storage."
        ),
        responses={
            200: openapi.Response(
                description="Role-specific dashboard data.",
                examples={
                    "application/json": {
                        "dashboard_greeting": "Welcome Landowner JohnDoe!",
                        "tutorial_links": [
                            "https://storage.googleapis.com/agrario-static/tutorials/tutorial1.mp4",
                            "https://storage.googleapis.com/agrario-static/tutorials/tutorial2.mp4",
                        ],
                    }
                },
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing authentication token.",
                examples={
                    "application/json": {
                        "error": "Authentication token not provided."
                    }
                },
            ),
            403: openapi.Response(
                description="Forbidden - User account inactive.",
                examples={
                    "application/json": {
                        "error": "User account is inactive."
                    }
                },
            ),
            404: openapi.Response(
                description="Not Found - User does not exist.",
                examples={
                    "application/json": {
                        "error": "User does not exist."
                    }
                },
            ),
        },
    )
    def get(self, request):
        """
        Retrieve dashboard data based on the user's role and include tutorial links.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response({"error": "Authentication token not provided."}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        
        if not decoded_token:
            logger.warning("Failed to decode token or token expired.")
            return Response({"error": "Invalid or expired Firebase token."}, status=status.HTTP_401_UNAUTHORIZED)

        email = decoded_token.get("email")
        try:
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_active:
            return Response({"error": "User account is inactive."}, status=status.HTTP_403_FORBIDDEN)

        # Fallback to user model's role if not in the token
        # role = decoded_token.get("role") or user.role
        role = get_user_role(decoded_token, email)

        # Use the first part of the email as a placeholder for the username if it's None
        username = user.first_name or email.split("@")[0]
        tutorial_links = self.get_tutorial_links(role)
        dashboard_greeting = f"Welcome {role} {username}!"

        dashboard_data = {
            "dashboard_greeting": dashboard_greeting,
            "tutorial_links": tutorial_links,
            "role": role,
        }

        return Response(dashboard_data, status=status.HTTP_200_OK)

class MarketUserProfileView(viewsets.ViewSet):
    """
    ViewSet for managing MarketUser profiles, dynamically choosing serializers based on user role.
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def get_serializer_class(user):
        """
        Dynamically select the serializer based on the user's role.

        Args:
            user (MarketUser): The authenticated user.

        Returns:
            Serializer class based on the user's role or None if unsupported.
        """
        if user.role == "landowner":
            return LandownerProfileSerializer
        if user.role == "developer":
            return DeveloperProfileSerializer
        return None

    @staticmethod
    def get_authenticated_user(request):
        """
        Retrieve the authenticated user based on the Firebase token.

        Args:
            request: The HTTP request object.

        Returns:
            MarketUser instance or Response with error message.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response({"error": "Authentication token not provided."}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            return Response({"error": "Invalid or expired Firebase token."}, status=status.HTTP_401_UNAUTHORIZED)

        email = decoded_token.get("email")
        if not email:
            return Response({"error": "Email not found in token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            return MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)
        
    @swagger_auto_schema(
        operation_summary="Retrieve User Profile",
        operation_description="Get profile details of the authenticated user based on their role.",
        responses={
            200: openapi.Response(description="User profile data", examples={"application/json": {"key": "value"}}),
            401: openapi.Response(description="Authentication token not provided or invalid"),
            404: openapi.Response(description="User not found"),
        },
    )

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve the profile details of the authenticated user.

        Args:
            request: The HTTP request object.

        Returns:
            Response containing the user's profile data or an error message.
        """
        user = self.get_authenticated_user(request)
        if isinstance(user, Response):
            return user

        serializer_class = self.get_serializer_class(user)
        if not serializer_class:
            return Response({"error": "Unsupported role."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = serializer_class(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="Update User Profile",
        operation_description="Update profile details of the authenticated user based on their role.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "first_name": openapi.Schema(type=openapi.TYPE_STRING, description="First name"),
                "last_name": openapi.Schema(type=openapi.TYPE_STRING, description="Last name"),
                "phone_number": openapi.Schema(type=openapi.TYPE_STRING, description="Phone number"),
                "address": openapi.Schema(type=openapi.TYPE_STRING, description="Address"),
            },
        ),
        responses={
            200: openapi.Response(description="Profile updated successfully"),
            401: openapi.Response(description="Authentication token not provided or invalid"),
            400: openapi.Response(description="Validation errors or unsupported role"),
        },
    )

    def partial_update(self, request, *args, **kwargs):
        """
        Update the profile details of the authenticated user.

        Args:
            request: The HTTP request object.

        Returns:
            Response containing the updated profile data or an error message.
        """
        user = self.get_authenticated_user(request)
        if isinstance(user, Response):
            return user

        serializer_class = self.get_serializer_class(user)
        if not serializer_class:
            return Response({"error": "Unsupported role."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = serializer_class(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)



class FirebasePasswordResetRequestView(APIView):
    """
    View to handle password reset requests via Firebase.
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Request Password Reset",
        operation_description="Sends a password reset email to the user using Firebase Authentication.",
        tags=["Password Reset"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="The email address of the user requesting a password reset.",
                    example="john.doe@example.com",
                ),
            },
            required=["email"],
        ),
        responses={
            200: openapi.Response(
                description="Password reset email sent successfully.",
                examples={"application/json": {"message": "Password reset email sent successfully."}},
            ),
            400: openapi.Response(
                description="Bad Request - Invalid email address provided.",
                examples={"application/json": {"error": "Email is required."}},
            ),
        },
    )
 
    def post(self, request):
        email = request.data.get("email")

        # Validate email input
        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Generate password reset link
            reset_link = firebase_auth.generate_password_reset_link(email)
            if not reset_link:
                raise Exception("Failed to generate email action link.")

            # Send the reset link to the user's email
            send_mail(
                subject="Password Reset Request",
                message=f"Click the link below to reset your password:\n{reset_link}",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )

            return Response(
                {"message": "Password reset email has been sent to your email address."},
                status=status.HTTP_200_OK,
            )
        except firebase_auth.UserNotFoundError:
            return Response(
                {"error": "Email not found in Firebase system."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )