from django.contrib.auth import get_user_model

def ensure_agrario_support_user():
    User = get_user_model()
    agrario_support_email = "support@agrario.com"
    user, created = User.objects.get_or_create(
        email=agrario_support_email,
        defaults={
            "first_name": "Agrario",
            "last_name": "Support",
            "is_superuser": True,
            "is_staff": True,
            "password": "defaultpassword",
        },
    )
    return user
