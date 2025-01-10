from rest_framework.routers import DefaultRouter
from .views import MessageViewSet, ChatViewSet

router = DefaultRouter()
router.register(r'messages', MessageViewSet, basename='messages')
router.register(r'chats', ChatViewSet, basename='chats')

urlpatterns = router.urls
