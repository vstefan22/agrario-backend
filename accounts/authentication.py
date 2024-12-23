"""Authentication backend for the accounts application.

Provides a custom authentication mechanism that verifies email confirmation
before granting access.
"""

from django.contrib.auth.backends import BaseBackend

from .models import MarketUser


class EmailConfirmedAuthenticationBackend(BaseBackend):
    """
    Custom authentication backend that uses email for authentication
    and ensures the user's email is confirmed.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a user by their email and password.

        Args:
            request: The HTTP request object.
            username: The email address of the user.
            password: The user's password.
            **kwargs: Additional keyword arguments.

        Returns:
            MarketUser instance if authentication is successful, otherwise None.
        """
        try:
            user = MarketUser.objects.get(username=username)
            if user.check_password(password) and user.is_email_confirmed:
                return user
        except MarketUser.DoesNotExist:
            pass
        return None

    def get_user(self, user_id):
        """
        Retrieve a user instance by their ID.

        Args:
            user_id: The ID of the user to retrieve.

        Returns:
            MarketUser instance if found, otherwise None.
        """
        try:
            return MarketUser.objects.get(pk=user_id)
        except MarketUser.DoesNotExist:
            pass
        return None
