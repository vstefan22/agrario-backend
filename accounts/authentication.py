from django.contrib.auth.backends import BaseBackend
from .models import MarketUser

class EmailConfirmedAuthenticationBackend(BaseBackend):
    """
    Custom authentication backend that uses email for authentication
    and ensures the user's email is confirmed.
    """

    def authenticate(self, request, username, password=None, **kwargs):
        try:
            # Fetch user by email explicitly
            user = MarketUser.objects.get(username=username)
            if user.check_password(password) and user.is_email_confirmed:
                return user
        except MarketUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return MarketUser.objects.get(pk=user_id)
        except MarketUser.DoesNotExist:
            return None
