from rest_framework.routers import DefaultRouter
from accounts.views import MarketUserViewSet, ConfirmEmailView, LoginView
from django.urls import path, include
from django.contrib import admin

router = DefaultRouter()
router.register(r'users', MarketUserViewSet, basename='market-user')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include(router.urls)),
    path('api/accounts/confirm-email/<uidb64>/<token>/',
         ConfirmEmailView.as_view(), name='confirm-email'),
    path('api/accounts/login/', LoginView.as_view(), name='login'),
]
