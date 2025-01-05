from .models import MarketUser
import logging

logger = logging.getLogger(__name__)

def get_user_role(decoded_token, user_email):
    """
    Retrieve the user role from the decoded Firebase token or database.

    Args:
        decoded_token (dict): The decoded Firebase token.
        user_email (str): The email of the user.

    Returns:
        str: The user's role, or None if not found.
    """
    # Try to get the role from the token
    role = decoded_token.get("role")
    if role:
        return role

    # Fallback to database if role is not in token
    try:
        user = MarketUser.objects.get(email=user_email)
        return user.role
    except MarketUser.DoesNotExist:
        logger.error(f"MarketUser with email {user_email} does not exist.")
        return None
