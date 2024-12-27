from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Message
from .serializers import MessageSerializer, ThreadSummarySerializer
from rest_framework import status, viewsets
from django.db import models
from django.db.models import Q, Max, Count
from accounts.models import MarketUser
import uuid

class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing messages between users.
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Retrieve messages involving the authenticated user.
        """
        user = self.request.user
        queryset = Message.objects.filter(
            Q(sender=user) | Q(recipient=user)
        )
        sort_by = self.request.query_params.get('sort_by', 'created_at')
        return queryset.order_by(sort_by)

    def create(self, request, *args, **kwargs):
        """
        Create a new message and assign a thread.
        """
        user = request.user  # The sender is the logged-in user
        data = request.data
        data['sender'] = user.id  # Automatically assign the sender

        try:
            recipient = MarketUser.objects.get(identifier=data['recipient'])
        except MarketUser.DoesNotExist:
            return Response({"recipient": "Invalid recipient - user does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        # Check for existing thread
        existing_thread = Message.objects.filter(
            Q(sender=user, recipient=recipient) |
            Q(sender=recipient, recipient=user)
        ).values_list('thread', flat=True).first()

        # Assign the thread programmatically
        data['thread'] = existing_thread if existing_thread else uuid.uuid4()

        # Serialize and save the message
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='threads')
    def list_threads(self, request):
        """
        Retrieve a summary of all threads involving the authenticated user.
        """
        user = request.user
        threads = Message.objects.filter(
            Q(sender=user) | Q(recipient=user)
        ).values(
            'thread'
        ).annotate(
            last_message=Max('created_at'),
            last_message_body=Max('body'),
            unread_count=Count('id', filter=Q(recipient=user, is_read=False)),
            participant=Max('recipient__id')
        ).order_by('-last_message')

        serializer = ThreadSummarySerializer(threads, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='mark-as-read')
    def mark_as_read(self, request, pk=None):
        """
        Mark all messages in a thread as read for the authenticated user.
        """
        user = request.user
        messages = Message.objects.filter(thread=pk, recipient=user, is_read=False)

        if not messages.exists():
            return Response(
                {"message": "No unread messages found in this thread."},
                status=status.HTTP_200_OK,
            )

        messages.update(is_read=True)
        return Response(
            {"message": f"{messages.count()} messages marked as read."},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        """
        Allow only the sender or recipient to delete a message.
        """
        instance = self.get_object()
        if instance.sender != request.user and instance.recipient != request.user:
            return Response({"error": "You are not authorized to delete this message."}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)