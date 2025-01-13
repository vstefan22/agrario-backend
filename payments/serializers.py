from rest_framework import serializers
from .models import PaymentTransaction

class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = "__all__"

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value

    def validate_currency(self, value):
        supported_currencies = ["usd", "eur"]
        if value.lower() not in supported_currencies:
            raise serializers.ValidationError(f"Currency {value} is not supported.")
        return value
