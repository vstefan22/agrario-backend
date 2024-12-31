import uuid
from django.db import models
from accounts.models import MarketUser
import logging
logger = logging.getLogger(__name__)

class Attachment(models.Model):
    file = models.FileField(upload_to="messages/attachments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    """
    Model representing a message between two MarketUser instances.
    """
    SUBJECT_CHOICES = [
        ('General Inquiry', 'General Inquiry'),
        ('Auction Question', 'Auction Question'),
        ('Support Request', 'Support Request'),
    ]
    identifier = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    sender = models.ForeignKey(
        MarketUser,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )
    recipient = models.ForeignKey(
        MarketUser,
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
    thread = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )
    is_admin_message = models.BooleanField(default=False)  # For admin messaging
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    read = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    attachments = models.ManyToManyField(
        'Attachment',
        blank=True,
        related_name='messages'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['sender', 'recipient', 'thread'],
                name='unique_thread_per_pair'
            )
        ]



    def __str__(self):
        return f"Message from {self.sender} to {self.recipient} - {self.subject}"
    

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        logger.info(f"Saved message {self.identifier} with thread {self.thread}")

