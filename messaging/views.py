from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from .models import Message, Chat, Attachment
from .serializers import MessageSerializer, ChatSerializer
from rest_framework import status, viewsets
from django.db import models
from django.db.models import Q, Max, Count
from accounts.models import MarketUser
import uuid
import logging
from rest_framework.exceptions import ValidationError, PermissionDenied
logger = logging.getLogger(__name__)


class ChatViewSet(viewsets.ModelViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        """
        Return chats associated with the authenticated user.
        """
        user = self.request.user
        return Chat.objects.filter(models.Q(user1=user))

    @action(detail=False, methods=['get'], url_path='my-chats')
    def my_chats(self, request):
        """
        Retrieve all chats for the logged-in user.
        """
        chats = self.get_queryset()
        serializer = self.get_serializer(chats, many=True)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        sender = self.request.user
        admins = (
            MarketUser.objects.filter(is_superuser=True)
            .annotate(
                chat_count=Count('chats_as_user1') + Count('chats_as_user2'),
                message_count=Count('received_messages')
            )
            .order_by('chat_count', 'message_count')
        )

        least_chats_admin = admins.first()

        if not least_chats_admin:
            raise serializers.ValidationError("No superusers available to receive the message.")

        chat = Chat.objects.filter(
            Q(user1=sender, user2=least_chats_admin) | Q(user1=least_chats_admin, user2=sender)
        ).first()

        if not chat:
            chat = Chat.objects.create(user1=sender, user2=least_chats_admin)

        serializer.validated_data['is_admin_message'] = True

        serializer.save(sender=sender, chat=chat, recipient=least_chats_admin)


    @action(detail=True, methods=['get'], url_path='conversation')
    def get_conversation(self, request, pk=None):
        """
        Retrieve all messages in the same chat.
        """
        user = request.user
        chat = Chat.objects.filter(identifier=pk).first()
        if not chat:
            return Response({"error": "Chat not found."}, status=status.HTTP_404_NOT_FOUND)

        messages = Message.objects.filter(chat=chat).order_by('created_at')
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Archive a message instead of deleting it.
        """
        instance = self.get_object()
        if instance.recipient != request.user:
            return Response({"error": "You cannot delete this message."}, status=status.HTTP_403_FORBIDDEN)

        instance.archived = True
        instance.save()
        return Response({"message": "Message archived successfully."}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """
        Get the count of unread messages for the logged-in user.
        """
        user = self.request.user
        count = Message.objects.filter(recipient=user, is_read=False).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], url_path='mark-as-read')
    def mark_as_read(self, request, pk=None):
        """
        Mark all messages in a chat as read.
        """
        user = request.user
        chat = Chat.objects.filter(identifier=pk).first()
        if not chat:
            return Response({"error": "Chat not found."}, status=status.HTTP_404_NOT_FOUND)
        if chat.user1 != user and chat.user2 != user:
            return Response({"error": "You are not part of this chat."}, status=status.HTTP_403_FORBIDDEN)

        # Mark messages as read
        Message.objects.filter(chat=chat, recipient=user,
                                is_read=False).update(is_read=True)
        return Response({"message": "Messages marked as read."}, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single message and mark it as read if the authenticated user is part of the chat.
        """
        instance = self.get_object()
        user = request.user

        # Mark the message as read only if the user is part of the chat
        if (instance.chat.user1 == user or instance.chat.user2 == user) and not instance.is_read:
            instance.is_read = True
            instance.save(update_fields=["is_read"])

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='admin-message')
    def admin_message(self, request):
        """
        Allow superusers to send admin messages to a specific user.
        """
        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can send admin messages.")

        recipient_id = request.data.get("recipient_id")
        subject = request.data.get("subject", "Admin Message")
        body = request.data.get("body", "")

        if not recipient_id:
            return Response({"error": "Recipient ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        recipient = MarketUser.objects.filter(identifier=recipient_id).first()
        if not recipient:
            return Response({"error": "Recipient not found."}, status=status.HTTP_404_NOT_FOUND)

        message = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            subject=subject,
            body=body,
            is_admin_message=True
        )

        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='broadcast')
    def broadcast_message(self, request):
        """
        Allow superusers to send a broadcast message to all users.
        """
        if not request.user.is_superuser:
            raise PermissionDenied(
                "Only superusers can send broadcast messages.")

        subject = request.data.get("subject", "Broadcast Message")
        body = request.data.get("body", "")

        # Retrieve all users
        users = MarketUser.objects.all()
        messages = [
            Message(
                sender=request.user,
                recipient=user,
                subject=subject,
                body=body,
                is_admin_message=True
            )
            for user in users
        ]

        Message.objects.bulk_create(messages)

        return Response({"message": "Broadcast sent successfully."}, status=status.HTTP_201_CREATED)
