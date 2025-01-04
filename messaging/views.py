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
from rest_framework.exceptions import ValidationError
logger = logging.getLogger(__name__)
from rest_framework.pagination import PageNumberPagination


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
        return Chat.objects.filter(models.Q(user1=user) | models.Q(user2=user))

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

    def get_queryset(self):
        """
        Retrieve messages related to chats involving the authenticated user.
        """
        user = self.request.user
        return Message.objects.filter(
            models.Q(chat__user1=user) | models.Q(chat__user2=user),
            archived=False
        ).order_by(self.request.query_params.get('sort_by', '-created_at'))  # Default: newest first

    def perform_create(self, serializer):
        """
        Handle creating a new message, including attaching files and checking for a chat.
        """
        sender = self.request.user
        recipient_id = self.request.data.get("recipient_id")

        if not recipient_id:
            raise ValidationError({"recipient_id": "Recipient ID is required."})

        recipient = MarketUser.objects.filter(identifier=recipient_id).first()
        if not recipient:
            raise ValidationError({"recipient_id": "Recipient not found."})

        chat, created = Chat.objects.get_or_create(user1=sender, user2=recipient)

        # Attach previous messages in the same chat
        previous_messages = Message.objects.filter(chat=chat).order_by('created_at')
        serializer.context['previous_messages'] = previous_messages

        serializer.save(sender=sender, chat=chat)

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

        # Mark messages as read
        Message.objects.filter(chat=chat, recipient=user, is_read=False).update(is_read=True)
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
