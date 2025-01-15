"""
Firebase authentication module.

Handles Firebase authentication and user management integration with Django.
"""

import logging, requests
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

def refresh_firebase_token(refresh_token):
    """
    Refresh Firebase access token using the refresh token.

    Args:
        refresh_token (str): The user's refresh token.

    Returns:
        dict: Contains new access_token and refresh_token.
    """
    firebase_api_key = settings.FIREBASE_API_KEY
    url = f"https://securetoken.googleapis.com/v1/token?key={firebase_api_key}"
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    response = requests.post(url, data=payload)
    
    if response.status_code != 200:
        logger.error(f"Failed to refresh token: {response.json()}")
        raise AuthenticationFailed("Invalid or expired refresh token.")

    data = response.json()
    
    return {
        "firebase_token": data["id_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data["expires_in"]
    }

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
            refresh_token = request.data.get("refresh_token") or request.headers.get("Refresh-Token")
            
            if refresh_token:
                try:
                    new_tokens = refresh_firebase_token(refresh_token)
                    token = new_tokens["firebase_token"]  # Umesto access_token
                    decoded_token = verify_firebase_token(token)

                    if not decoded_token:
                        raise AuthenticationFailed({"error": "Invalid or expired Firebase token after refresh."})

                except AuthenticationFailed:
                    raise AuthenticationFailed({"error": "Session expired. Please log in again."})
            else:
                raise AuthenticationFailed({"error": "Invalid or expired Firebase token."})

        email = decoded_token.get("email")
        if not email:
            raise AuthenticationFailed({"error": "Email not found in Firebase token."})

        try:
            with transaction.atomic():
                user, created = MarketUser.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email.split("@")[0],
                        "is_superuser": decoded_token.get("is_superuser", False),
                        "is_staff": decoded_token.get("is_superuser", False),
                    },
                )
        except Exception as e:
            raise AuthenticationFailed({"error": "Failed to authenticate user."}) from e

        return (user, None)
