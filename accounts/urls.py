from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import MarketUserViewSet, ConfirmEmailView, LoginView

router = DefaultRouter()
router.register(r'users', MarketUserViewSet, basename='market-user')

urlpatterns = router.urls + [
    path('confirm-email/<uidb64>/<token>/', ConfirmEmailView.as_view(), name='confirm-email'),
    path('login/', LoginView.as_view(), name='login'),
]
