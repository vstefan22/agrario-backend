"""Serializers for the Marketplace application.

Defines serializers for users, landowners, project developers, and dashboards.
"""

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from offers.models import AreaOffer, Parcel
from offers.serializers import AreaOfferSerializer, ParcelSerializer

from .models import Landowner, MarketUser, ProjectDeveloper


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the MarketUser model.

    Handles user creation, updates, and password validation.
    """

    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = MarketUser
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "address",
            "role",
            "is_email_confirmed",
            "password",
            "confirm_password",
        ]
        read_only_fields = ["id", "is_email_confirmed", "role"]

    def validate(self, attrs):
        """
        Validate that passwords match.
        """
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError({"password": "Passwords must match."})
        return attrs

    def create(self, validated_data):
        """
        Create a new MarketUser instance.
        """
        validated_data.pop("confirm_password")
        user = MarketUser.objects.create(
            username=validated_data["username"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            email=validated_data["email"],
        )
        user.set_password(validated_data["password"])
        user.save()
        return user

    def update(self, instance, validated_data):
        """
        Update an existing MarketUser instance.
        """
        validated_data.pop("password", None)
        validated_data.pop("confirm_password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.

    Handles user creation during registration and email confirmation.
    """

    invite_code = serializers.CharField(write_only=True, required=False)
    role = serializers.ChoiceField(choices=MarketUser.ROLE_CHOICES)

    class Meta:
        model = MarketUser
        fields = ["username", "email", "password", "invite_code", "role"]

    def create(self, validated_data):
        """
        Create a new MarketUser during registration.
        """
        validated_data.pop("invite_code", None)
        role = validated_data.pop("role", "landowner")
        user = MarketUser.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            role=role,
        )
        return user

    def send_confirmation_email(self, user):
        """
        Generate and send an email confirmation link.
        """
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        confirmation_link = reverse(
            "confirm-email", kwargs={"uidb64": uid, "token": token}
        )
        send_mail(
            subject="Confirm Your Email Address",
            message = (
                f"Hi {user.username},\n\n"
                f"Click the link below to confirm your email:\n"
                f"http://localhost:8000{confirmation_link}"
            ),
            from_email="noreply@example.com",
            recipient_list=[user.email],
        )


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.

    Validates email and password credentials.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """
        Validate user credentials.
        """
        email = attrs.get("email")
        password = attrs.get("password")

        try:
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist as exc:
            raise serializers.ValidationError(_("Invalid email or password.")) from exc

        if not user.check_password(password):
            raise serializers.ValidationError(_("Invalid email or password."))

        if not user.is_email_confirmed:
            raise serializers.ValidationError(
                _("Please confirm your email before logging in.")
            )

        attrs["user"] = user
        return attrs

    def create(self, _validated_data):
        pass

    def update(self, _instance, _validated_data):
        pass


class LandownerDashboardSerializer(serializers.ModelSerializer):
    """
    Serializer for Landowner dashboard data.

    Provides details about parcels and offers related to the landowner.
    """

    parcels = serializers.SerializerMethodField()
    offers = serializers.SerializerMethodField()

    class Meta:
        model = Landowner
        fields = ["id", "username", "email", "parcels", "offers"]

    def get_parcels(self, obj):
        """
        Retrieve parcels created by the landowner.
        """
        parcels = Parcel.objects.filter(created_by=obj)
        return ParcelSerializer(parcels, many=True).data

    def get_offers(self, obj):
        """
        Retrieve area offers created by the landowner.
        """
        offers = AreaOffer.objects.filter(created_by=obj)
        return AreaOfferSerializer(offers, many=True).data


class DeveloperDashboardSerializer(serializers.ModelSerializer):
    """
    Serializer for Project Developer dashboard data.

    Provides details about the developer's watchlist and active auctions.
    """

    watchlist = serializers.SerializerMethodField()
    auctions = serializers.SerializerMethodField()

    class Meta:
        model = ProjectDeveloper
        fields = ["id", "username", "email", "watchlist", "auctions"]

    def get_watchlist(self, obj):
        """
        Retrieve parcels in the developer's watchlist.
        """
        watchlist = obj.projectdeveloperwatchlist_set.all()
        return ParcelSerializer([item.parcel for item in watchlist], many=True).data

    def get_auctions(self, _obj):
        """
        Retrieve active auctions.
        """
        auctions = AreaOffer.objects.filter(status="ACTIVE")
        return AreaOfferSerializer(auctions, many=True).data
