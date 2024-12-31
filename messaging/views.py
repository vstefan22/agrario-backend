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
import logging
logger = logging.getLogger(__name__)

class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing messages between users.
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Retrieve filtered and sorted messages involving the authenticated user.
        """
        user = self.request.user
        queryset = Message.objects.filter(
            models.Q(sender=user) | models.Q(recipient=user)
        )

        # Apply filters
        subject = self.request.query_params.get('subject')
        if subject:
            queryset = queryset.filter(subject__icontains=subject)

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(created_at__range=[start_date, end_date])

        participant_id = self.request.query_params.get('participant')
        if participant_id:
            queryset = queryset.filter(
                models.Q(sender__identifier=participant_id) |
                models.Q(recipient__identifier=participant_id)
            )

        # Apply sorting
        sort_by = self.request.query_params.get('sort_by', 'created_at')
        return queryset.order_by(sort_by)

    def create(self, request, *args, **kwargs):
        """
        Create a new message and strictly assign an existing thread if it exists.
        """
        user = request.user
        data = request.data
        data["sender"] = user.id

        try:
            recipient = MarketUser.objects.get(identifier=data["recipient"])
        except MarketUser.DoesNotExist:
            return Response({"error": "Invalid recipient - user does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        # Check for an existing thread
        existing_thread = Message.objects.filter(
            models.Q(sender=user, recipient=recipient) |
            models.Q(sender=recipient, recipient=user)
        ).values_list("thread", flat=True).first()

        if existing_thread:
            # If a thread exists, force its use
            data["thread"] = existing_thread
            logger.info(f"Using existing thread: {existing_thread}")
        else:
            # If no thread exists, prevent creating a new thread
            return Response(
                {"error": "No existing thread found between the sender and recipient. Start a new conversation explicitly."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Serialize and save the message
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()

        logger.info(f"Message saved with thread: {message.thread}")
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
                participant_count=Count('id', distinct=True)  # New metadata
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
        Archive a message instead of deleting it.
        """
        instance = self.get_object()
        if instance.sender != request.user and instance.recipient != request.user:
            return Response({"error": "You are not authorized to delete this message."}, status=status.HTTP_403_FORBIDDEN)
        instance.archived = True  # archive the message instead of deleting
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['post'], url_path='admin-messages')
    def admin_messages(self, request):
        """
        Endpoint for platform admins to send messages to users.
        """
        if not request.user.is_staff:  # Assuming `is_staff` denotes admin users
            return Response({"error": "You are not authorized to send admin messages."}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        data['sender'] = request.user.id
        data['is_admin_message'] = True

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """
        Retrieve the count of unread messages for the authenticated user.
        """
        user = request.user
        count = Message.objects.filter(recipient=user, is_read=False).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)