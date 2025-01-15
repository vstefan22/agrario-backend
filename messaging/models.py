import uuid
from django.db import models
from accounts.models import MarketUser
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class Attachment(models.Model):
    """
    Model for storing file attachments for messages.
    """
    file = models.FileField(upload_to="messages/attachments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class Chat(models.Model):
    identifier = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chats_as_user1'
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chats_as_user2'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat {self.identifier} between {self.user1} and {self.user2}"


class Message(models.Model):
    SUBJECT_CHOICES = [
        ('Flurstücksanalyse PLUS', 'Flurstücksanalyse PLUS'),
        ('Angebot erstellen', 'Angebot erstellen'),
        ('Sonstiges', 'Sonstiges'),
    ]
    identifier = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    chat = models.ForeignKey(
        'Chat',
        on_delete=models.CASCADE,
        related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages"
    )
    subject = models.CharField(
        max_length=64,
        choices=SUBJECT_CHOICES,
        default='General Inquiry',
    )
    body = models.TextField(
        max_length=500,
        blank=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_admin_message = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    attachments = models.ManyToManyField(
        'Attachment',
        blank=True,
        related_name='messages'
    )

    class Meta:
        ordering = ['created_at']  # Messages are ordered by creation time

    def __str__(self):
        return f"Message in Chat {self.chat.identifier} from {self.sender} - {self.subject}"
