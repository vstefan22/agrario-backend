from rest_framework import serializers
from .models import MarketUser
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = MarketUser
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'password', 'confirm_password']

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({"password": "Passwords must match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = MarketUser.objects.create(
            username=validated_data['username'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            email=validated_data['email']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def update(self, instance, validated_data):
        validated_data.pop('password', None)
        validated_data.pop('confirm_password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

class UserRegistrationSerializer(serializers.ModelSerializer):
    invite_code = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = MarketUser
        fields = ['username', 'email', 'password', 'invite_code']

    def create(self, validated_data):
        validated_data.pop('invite_code', None)  # Remove invite_code; it's not part of the model
        user = MarketUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
        )
        return user

    def send_confirmation_email(self, user):
        """
        Generate a confirmation link and send an email.
        """
        # Generate email confirmation token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Use Django's reverse to generate the URL
        from django.urls import reverse
        confirmation_link = reverse(
            'confirm-email', kwargs={'uidb64': uid, 'token': token}
        )

        # Send the email
        send_mail(
            subject="Confirm Your Email Address",
            message=f"Hi {user.username},\n\nClick the link below to confirm your email:\nhttp://localhost:8000{confirmation_link}",
            from_email="noreply@example.com",
            recipient_list=[user.email],
        )

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()  # Enforces valid email format
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        # Authenticate using email
        try:
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            raise serializers.ValidationError(_("Invalid email or password."))

        if not user.check_password(password):
            raise serializers.ValidationError(_("Invalid email or password."))

        # Check if the email is confirmed
        if not user.is_email_confirmed:
            raise serializers.ValidationError(_("Please confirm your email before logging in."))

        attrs['user'] = user
        return attrs