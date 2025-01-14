from rest_framework import serializers
from .models import Message, Attachment, Chat
from accounts.models import MarketUser
import uuid


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ['id', 'file', 'uploaded_at']

    def validate_file(self, value):
        max_size = 5 * 1024 * 1024  # 5 MB
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
        if value.size > max_size:
            raise serializers.ValidationError("File size must be under 5MB.")
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Unsupported file type.")
        return value


class SenderSerializer(serializers.ModelSerializer):
    """
    Serializer for the sender details.
    """
    class Meta:
        model = MarketUser
        fields = ['id', 'email']



class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)  # Display sender in response
    is_admin_message = serializers.BooleanField(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    attachment_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Message
        fields = (
            'identifier', 'sender', 'subject', 'body', 'attachments',
            'attachment_files', 'created_at', 'is_read', 'is_admin_message'
        )
        read_only_fields = ['identifier', 'created_at', 'is_read', 'attachments', 'sender', 'is_admin_message']

    def create(self, validated_data):
        # Extract and remove `chat` from validated_data to avoid duplicate keyword arguments
        chat = validated_data.pop('chat', None)

        # Handle attachment files
        attachment_files = validated_data.pop('attachment_files', [])

        # Create the message
        message = Message.objects.create(chat=chat, **validated_data)

        # Add attachments
        for file in attachment_files:
            attachment = Attachment.objects.create(file=file)
            message.attachments.add(attachment)

        return message
    

class ChatSerializer(serializers.ModelSerializer):
    user1 = serializers.StringRelatedField()  # Display user1 username
    user2 = serializers.StringRelatedField()  # Display user2 username
    messages_count = serializers.SerializerMethodField()  # Count of messages in chat

    class Meta:
        model = Chat
        fields = ['identifier', 'user1', 'user2', 'created_at', 'messages_count']

    def get_messages_count(self, obj):
        """
        Count messages in the chat.
        """
        return obj.messages.count()