"""
Firebase authentication module.

Handles Firebase authentication and user management integration with Django.
"""

import logging
logger = logging.getLogger(__name__)
from django.db import transaction
import firebase_admin
from firebase_admin import auth, credentials
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import MarketUser
from .utils import get_user_role

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(settings.FIREBASE_CONFIG)
        firebase_admin.initialize_app(cred)
    except Exception as e:
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
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        return decoded_token
    except auth.RevokedIdTokenError:
        logger.error("Token has been revoked.")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
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
    except auth.EmailAlreadyExistsError:
        raise AuthenticationFailed({"error": "The email address is already in use."})
    except auth.InvalidPasswordError:
        raise AuthenticationFailed({"error": "The password is invalid or too weak."})
    except Exception as e:
        logger.error(f"Firebase user creation error: {str(e)}")
        raise AuthenticationFailed({"error": "Could not create Firebase user. Please check the details."}) from e

class FirebaseAuthentication(BaseAuthentication):
    """
    Custom authentication class for Firebase Authentication.
    """
    

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split("Bearer ")[1]
        decoded_token = verify_firebase_token(token)
        if not decoded_token:
            raise AuthenticationFailed({"error": "Invalid or expired Firebase token."})

        email = decoded_token.get("email")
        if not email:
            raise AuthenticationFailed({"error": "Email not found in Firebase token."})

        # Example: Identify superuser by Firebase custom claims
        is_superuser = decoded_token.get("is_superuser", False)

        try:
            with transaction.atomic():
                user, created = MarketUser.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email.split("@")[0],
                        "is_superuser": is_superuser,
                        "is_staff": is_superuser,
                    },
                )

                # Update existing user superuser status if needed
                if user.is_superuser != is_superuser:
                    user.is_superuser = is_superuser
                    user.is_staff = is_superuser
                    user.save(update_fields=["is_superuser", "is_staff"])

        except Exception as e:
            raise AuthenticationFailed({"error": "Failed to authenticate user."}) from e

        return (user, None)
