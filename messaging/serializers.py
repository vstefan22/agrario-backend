from rest_framework import serializers
from .models import Message, Attachment
from accounts.models import MarketUser
import uuid


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ['id', 'file', 'uploaded_at']


class SenderSerializer(serializers.ModelSerializer):
    """
    Serializer for the sender details.
    """
    class Meta:
        model = MarketUser
        fields = ['id', 'username', 'email']


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for messages, including sender, recipient, and thread details.
    """
    sender = SenderSerializer(read_only=True)
    recipient = serializers.UUIDField()
    is_read = serializers.BooleanField(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    attachment_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Message
        fields = [
            'identifier', 'sender', 'recipient', 'subject', 'body',
            'thread', 'created_at', 'is_read', 'attachments', 'attachment_files'
        ]
        read_only_fields = ['identifier', 'thread', 'created_at', 'sender', 'attachments']

    def create(self, validated_data):
        # Extract attachment_files from validated_data
        attachment_files = validated_data.pop('attachment_files', [])

        # Ensure the sender is included from the context (authenticated user)
        validated_data['sender'] = self.context['request'].user

        # Create the message object
        message = Message.objects.create(**validated_data)

        # Save attachments and link them to the message
        for file in attachment_files:
            attachment = Attachment.objects.create(file=file)
            message.attachments.add(attachment)

        return message

    def validate_recipient(self, value):
        """
        Validate the recipient field to ensure the user exists.
        """
        # Ensure the value is a UUID instance
        if not isinstance(value, uuid.UUID):
            try:
                value = uuid.UUID(value)
            except ValueError:
                raise serializers.ValidationError("Recipient must be a valid UUID.")

        # Check if the recipient exists in the database
        try:
            recipient = MarketUser.objects.get(identifier=value)
        except MarketUser.DoesNotExist:
            raise serializers.ValidationError("Recipient does not exist.")
        
        return recipient


class ThreadSummarySerializer(serializers.Serializer):
    """
    Serializer to provide a summary of threads involving the user.
    """
    thread = serializers.UUIDField()
    last_message = serializers.CharField()
    last_message_time = serializers.DateTimeField()
    unread_count = serializers.IntegerField()
    participant = SenderSerializer()
