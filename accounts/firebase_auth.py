import firebase_admin
from firebase_admin import auth, credentials
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import MarketUser
import logging

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(settings.FIREBASE_CONFIG)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.error("Failed to initialize Firebase Admin SDK: %s", e)
        raise

def verify_firebase_token(token):
    """
    Verify the Firebase ID token.

    Args:
        token (str): The Firebase ID token.

    Returns:
        dict: The decoded token if valid, None otherwise.
    """
    try:
        return auth.verify_id_token(token)
    except Exception as e:
        logger.error("Failed to verify Firebase token: %s", e)
        return None

def create_firebase_user(email, password):
    """
    Create a Firebase user.

    Args:
        email (str): The user's email.
        password (str): The user's password.

    Returns:
        firebase_admin.auth.UserRecord: The created Firebase user.
    """
    try:
        return auth.create_user(email=email, password=password)
    except Exception as e:
        logger.error("Failed to create Firebase user: %s", e)
        raise AuthenticationFailed("Could not create Firebase user.")

class FirebaseAuthentication(BaseAuthentication):
    """
    Custom authentication class for Firebase Authentication.
    """

    def authenticate(self, request):
        # Extract token from the "Authorization" header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None  # No authentication header provided
        if not auth_header.startswith("Bearer "):
            raise AuthenticationFailed("Invalid token format. Token must start with 'Bearer '.")

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            raise AuthenticationFailed("Invalid or expired Firebase token.")

        email = decoded_token.get("email")
        if not email:
            raise AuthenticationFailed("Email not found in Firebase token.")

        # Fetch or create the user
        user, _ = MarketUser.objects.get_or_create(
            email=email,
            defaults={"username": email.split("@")[0]},
        )
        return (user, None)
