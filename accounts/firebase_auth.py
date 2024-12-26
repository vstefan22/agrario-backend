"""
Firebase authentication module.

Handles Firebase authentication and user management integration with Django.
"""

import logging

import firebase_admin
from firebase_admin import auth, credentials
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import MarketUser

# Initialize logging
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(settings.FIREBASE_CONFIG)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.error("Failed to initialize Firebase Admin SDK: %s", e)
        raise RuntimeError("Firebase initialization error") from e

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

    Raises:
        AuthenticationFailed: If user creation fails.
    """
    try:
        return auth.create_user(email=email, password=password)
    except Exception as e:
        logger.error("Failed to create Firebase user: %s", e)
        raise AuthenticationFailed(
            "Could not create Firebase user."
        ) from e

class FirebaseAuthentication(BaseAuthentication):
    """
    Custom authentication class for Firebase Authentication.
    """

    def authenticate(self, request):
        """
        Authenticate the user using Firebase ID token.

        Args:
            request: The HTTP request object.

        Returns:
            tuple: Authenticated user and token, or None.

        Raises:
            AuthenticationFailed: If token is invalid or authentication fails.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        if not auth_header.startswith("Bearer "):
            raise AuthenticationFailed(
                "Invalid token format. Token must start with 'Bearer '."
            )

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            raise AuthenticationFailed("Invalid or expired Firebase token.")

        email = decoded_token.get("email")
        if not email:
            raise AuthenticationFailed("Email not found in Firebase token.")

        try:
            user, _ = MarketUser.objects.get_or_create(
                email=email,
                defaults={"username": email.split("@")[0]},
            )
        except Exception as e:
            logger.error("Error fetching or creating user: %s", e)
            raise AuthenticationFailed("Failed to authenticate user.") from e

        return (user, None)
