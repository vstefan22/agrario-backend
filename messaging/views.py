from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Message
from .serializers import MessageSerializer
from rest_framework import status, viewsets
from django.db import models
from accounts.models import MarketUser
import uuid

class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Message.objects.filter(
            models.Q(sender=user) | models.Q(recipient=user)
        )
        sort_by = self.request.query_params.get('sort_by', 'created_at')
        return queryset.order_by(sort_by)

    def create(self, request, *args, **kwargs):
        user = request.user  # The sender is the logged-in user
        data = request.data
        data['sender'] = user.id  # Automatically assign the sender

        try:
            recipient = MarketUser.objects.get(identifier=data['recipient'])
        except MarketUser.DoesNotExist:
            return Response({"recipient": "Invalid recipient - user does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        # Check for existing thread
        existing_thread = Message.objects.filter(
            models.Q(sender=user, recipient=recipient) |
            models.Q(sender=recipient, recipient=user)
        ).values_list('thread', flat=True).first()

        # Assign the thread programmatically
        data['thread'] = existing_thread if existing_thread else uuid.uuid4()

        # Serialize and save the message
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=['get'], url_path='thread/(?P<thread_id>[^/.]+)')
    def thread(self, request, thread_id=None):
        user = request.user
        messages = Message.objects.filter(
            thread=thread_id
        ).filter(
            models.Q(sender=user) | models.Q(recipient=user)
        )
        if not messages.exists():
            return Response(
                {"error": "No messages found for the specified thread or you are not authorized."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.sender != request.user and instance.recipient != request.user:
            return Response({"error": "You are not authorized to delete this message."}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
