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
        fields = ['id', 'username', 'email']


class MessageSerializer(serializers.ModelSerializer):
    recipient_id = serializers.UUIDField(write_only=True)  # For input
    recipient = serializers.StringRelatedField(read_only=True)  # Display recipient in response
    sender = serializers.StringRelatedField(read_only=True)  # Display sender in response
    is_admin_message = serializers.BooleanField(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    attachment_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )
    previous_messages = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            'identifier', 'recipient_id', 'recipient', 'sender', 
            'subject', 'body', 'attachments', 'attachment_files', 
            'created_at', 'is_read', 'previous_messages', 'is_admin_message'
        )
        read_only_fields = ['identifier', 'created_at', 'is_read', 'attachments', 'sender', 'is_admin_message']

    def get_previous_messages(self, obj):
        """
        Retrieve previous messages from the same conversation.
        """
        previous_messages = self.context.get('previous_messages', [])
        return MessageSerializer(previous_messages, many=True).data

    def create(self, validated_data):
        attachment_files = validated_data.pop('attachment_files', [])
        sender = validated_data['sender']

        recipient_id = validated_data.pop('recipient_id')
        recipient = MarketUser.objects.filter(identifier=recipient_id).first()
        if not recipient:
            raise serializers.ValidationError({"recipient_id": "Recipient not found."})

        chat, created = Chat.objects.get_or_create(user1=sender, user2=recipient)

        message = Message.objects.create(chat=chat, **validated_data)

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