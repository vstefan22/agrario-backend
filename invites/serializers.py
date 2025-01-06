from rest_framework import serializers
from .models import InviteLink, PromoCode

class InviteLinkSerializer(serializers.ModelSerializer):
    """
    Serializer for InviteLink model.
    """
    class Meta:
        model = InviteLink
        fields = ['uri_hash', 'created_by', 'is_active', 'successful_referrals', 'created_at']


class PromoCodeSerializer(serializers.ModelSerializer):
    """
    Serializer for PromoCode model.
    """
    class Meta:
        model = PromoCode
        fields = ['code', 'created_by', 'assigned_to', 'redeemed_by', 'amount_percent', 'is_active', 'created_at']
