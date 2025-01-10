from django.contrib.auth.management.commands.createsuperuser import Command as BaseCreateSuperuserCommand
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from accounts.models import MarketUserManager


class Command(BaseCreateSuperuserCommand):
    """
    Custom implementation of the createsuperuser command
    with enforced password validation.
    """

    def handle(self, *args, **options):
        password = options.get("password")

        # Validate password length for Firebase
        if password and len(password) < 6:
            raise ValidationError(_("Password must be at least 6 characters long for Firebase."))

        # Call the original handle method to proceed with user creation
        super().handle(*args, **options)
