from django.contrib import admin
from .models import Message, Attachment, Chat

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Attachment model.
    """
    list_display = ('file', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('file',)
    readonly_fields = ['uploaded_at']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Message model.
    """
    list_display = ('subject', 'sender', 'created_at', 'is_admin_message', 'is_read')  # Use a custom method
    list_filter = ('created_at', 'sender', 'chat', 'is_admin_message')
    search_fields = ('subject', 'sender__email', 'body')  # Removed 'recipient__email'
    ordering = ('-created_at',)

    # def get_recipient(self, obj):
    #     return obj.recipient.all()

    def get_queryset(self, request):
        """
        Ensure related objects are prefetched for performance.
        """
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('attachments')


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("identifier", "created_at")
    search_fields = ("identifier",)
    list_filter = ("created_at",)

