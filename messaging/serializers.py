from rest_framework import serializers
from .models import Message
from accounts.models import MarketUser
import uuid

class SenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketUser
        fields = ['id', 'username', 'email']


class MessageSerializer(serializers.ModelSerializer):
    sender = SenderSerializer(read_only=True)
    recipient = serializers.UUIDField()

    class Meta:
        model = Message
        fields = ['identifier', 'sender', 'recipient', 'subject', 'body', 'thread', 'created_at']
        read_only_fields = ['identifier', 'thread', 'created_at', 'sender']

    def validate_recipient(self, value):
        """
        Validate the recipient field to ensure the user exists.
        """
        # Skip validation if value is already a MarketUser instance
        if isinstance(value, MarketUser):
            return value

        # Otherwise, validate as a UUID and fetch MarketUser
        try:
            value = uuid.UUID(value)  # Ensure it is a valid UUID
        except ValueError:
            raise serializers.ValidationError("Recipient must be a valid UUID.")

        try:
            recipient = MarketUser.objects.get(identifier=value)
        except MarketUser.DoesNotExist:
            raise serializers.ValidationError("Recipient does not exist.")
        return recipient

    def create(self, validated_data):
        """
        Ensure recipient is a MarketUser instance before saving.
        """
        validated_data['recipient'] = self.validate_recipient(validated_data['recipient'])
        return Message.objects.create(**validated_data)