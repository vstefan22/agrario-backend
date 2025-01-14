from django.apps import AppConfig


class MessagingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "messaging"

    def ready(self):
        from .utils import ensure_agrario_support_user
        ensure_agrario_support_user()
