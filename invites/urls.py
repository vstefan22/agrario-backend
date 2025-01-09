from django.urls import path
from .views import CreateInviteLinkView, ValidateInviteLinkView, RegisterWithInviteView, RedeemPromoCodeView

urlpatterns = [
    path('create/', CreateInviteLinkView.as_view(), name='create_invite_link'),
    path('validate/<str:code>/', ValidateInviteLinkView.as_view(), name='validate_invite_link'),
    path('register-with-invite/', RegisterWithInviteView.as_view(), name='register_with_invite'),
    path('promo/redeem/', RedeemPromoCodeView.as_view(), name='redeem_promo_code'),
]
