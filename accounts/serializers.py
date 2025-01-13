"""Serializers for the Marketplace application.

Defines serializers for users, landowners, project developers, and dashboards.
"""

import logging
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework import status
from offers.serializers import AreaOfferSerializer, ParcelSerializer
from django.conf import settings
from django.urls import reverse
logger = logging.getLogger(__name__)
from .models import Landowner, MarketUser, ProjectDeveloper, ProjectDeveloperInterest
from offers.models import AreaOffer


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
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "address",
            "role",
            "is_email_confirmed",
            "password",
            "confirm_password",
            "company_name",
            "company_website",
            "city",
            "zipcode",
            "profile_picture"
        ]
        read_only_fields = ["id", "is_email_confirmed", "role"]

    def validate(self, attrs):
        """
        Validate that passwords match.
        """
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError(
                {"error": "Passwords must match."})
        return attrs

    def create(self, request, *args, **kwargs):
        """
        Create a new user and enforce validation for mandatory fields.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        serializer.send_confirmation_email(user)
        return Response(
            {"message": "User registered successfully."},
            status=status.HTTP_201_CREATED,
        )

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
    Serializer for user registration with mandatory field validation.
    """
    confirm_password = serializers.CharField(write_only=True, required=True)  # Explicitly declare it here
    invite_code = serializers.CharField(write_only=True, required=False)
    role = serializers.ChoiceField(choices=MarketUser.ROLE_CHOICES)

    class Meta:
        model = MarketUser
        fields = [
            "first_name",
            "last_name",
            "email",
            "password",
            "confirm_password",
            "invite_code",
            "role",
            "phone_number",
            "address",
            "company_name",
            "company_website",
            "profile_picture",
            "zipcode",
            "city",
            "privacy_accepted",
            "terms_accepted",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "password": {"write_only": True, "required": True},
        }

    def validate(self, attrs):
        """
        Validate that mandatory fields are filled.
        """
        # Validate password confirmation
        if attrs["password"] != self.initial_data.get("confirm_password"):
            raise serializers.ValidationError({"password": "Passwords do not match."})

        mandatory_fields = ["email", "password", "role"]
        if attrs.get("role") == "landowner":
            mandatory_fields.extend(
                ["phone_number", "address", "zipcode", "city"])
        elif attrs.get("role") == "developer":
            mandatory_fields.extend(["company_name", "company_website"])

        for field in mandatory_fields:
            if not attrs.get(field):
                raise serializers.ValidationError(
                    {"error": f"{field} is required."})

        # Validate password strength
        if len(attrs["password"]) < 6:
            raise serializers.ValidationError(
                {"error": "Password must be at least 6 characters long."})

        return attrs

    def create(self, validated_data):
        """
        Create a new MarketUser during registration.
        """
        validated_data.pop("invite_code", None)
        validated_data.pop("invite_code", None)
        role = validated_data.pop("role", "landowner")
        user = MarketUser.objects.create_user(
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            password=validated_data["password"],
            role=role,
            phone_number=validated_data.get("phone_number"),
            address=validated_data.get("address"),
            company_name=validated_data.get("company_name"),
            company_website=validated_data.get("company_website"),
            profile_picture=validated_data.get("profile_picture"),
            zipcode=validated_data.get("zipcode"),
            city=validated_data.get("city"),
        )
        return user

    def send_confirmation_email(self, user):
        """
        Generate and send an email confirmation link to the user.
        """

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        confirmation_link = f"{settings.BACKEND_URL}{reverse('confirm-email', kwargs={'uidb64': uid, 'token': token})}"

        send_mail(
            subject="Confirm Your Email Address",
            message=f"Hi {user.first_name},\n\nClick the link below to confirm your email:\n{confirmation_link}",
            from_email=settings.EMAIL_HOST_USER,
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
            raise serializers.ValidationError(
                {"error": "Invalid email or password."}) from exc

        if not user.check_password(password):
            raise serializers.ValidationError(
                {"error": "Invalid email or password."})

        if not user.is_email_confirmed:
            raise serializers.ValidationError(
                {"error": "Please confirm your email before logging in."}
            )

        attrs["user"] = user
        return attrs

    def create(self, _validated_data):
        pass

    def update(self, _instance, _validated_data):
        pass


class LandownerDashboardSerializer(serializers.ModelSerializer):
    """
    Serializer for Landowner Dashboard data.
    Provides greeting, quick action links, notifications, and statistics.
    """

    # Tutorials
    tutorial_links = serializers.SerializerMethodField()

    # Notifications
    notifications = serializers.SerializerMethodField()

    # Parcels Overview
    statistics = serializers.SerializerMethodField()

    class Meta:
        model = Landowner
        fields = [
            "first_name",        # For personalized greeting
            "tutorial_links",   # List of tutorial video URLs
            "notifications",    # Notifications and unread message counts
            "statistics",       # Parcel statistics
        ]

    def get_tutorial_links(self, role):
        """
        Retrieves public links to tutorial videos based on the normalized role.
        """
        try:
            from google.cloud import storage
            from django.conf import settings

            # Ensure the role is normalized to a string
            if not isinstance(role, str):
                raise ValueError(f"Expected a string for role, got {type(role).__name__}")

            normalized_role = role.lower().strip()  # Normalize role to match bucket structure

            # Initialize Google Cloud Storage client using credentials
            storage_client = storage.Client(
                credentials=settings.GS_CREDENTIALS, project=settings.G_CLOUD_PROJECT_ID
            )
            bucket = storage_client.bucket(settings.G_CLOUD_BUCKET_NAME_STATIC)

            # Construct the prefix
            prefix = f"tutorials/{normalized_role}/"
            blobs = bucket.list_blobs(prefix=prefix)

            # Collect public URLs
            tutorial_links = [blob.public_url for blob in blobs if not blob.name.endswith("/")]

            # Log if no files are found
            if not tutorial_links:
                logger.warning(
                    f"No tutorial videos found for role: {normalized_role} in bucket with prefix: {prefix}"
                )

            return tutorial_links
        except Exception as e:
            logger.error(f"Error retrieving tutorial links for role '{role}': {e}")
            return []
        
    def get_notifications(self, obj):
        """
        Retrieve notifications (unread messages).
        """
        from messaging.models import Message  # Replace with actual model path

        unread_messages = Message.objects.filter(sender=obj, is_read=False).count()
        return {
            "unread_messages": unread_messages
        }

    def get_statistics(self, obj):
        """
        Return parcel statistics (owned and pending analysis).
        """
        return {
            "parcels_owned": obj.created_parcels.count(),
            "parcels_pending_analysis": obj.created_parcels.filter(status="pending_analysis").count(),
        }



class LandownerSerializer(serializers.ModelSerializer):
    """
    Serializer for Landowner-specific profile details.
    """

    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Landowner
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "address",
            "zipcode",
            "city",
            "company_name",
            "company_website",
            "profile_picture",
            "position",
            "password",
            "confirm_password",
            "role",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        """
        Validate that passwords match and required fields are present for create.
        """
        if self.instance:  # During update, skip mandatory field checks
            return attrs

        # Validate passwords during creation
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError({"password": "Passwords do not match."})

        # Check for mandatory fields during creation
        mandatory_fields = ["email", "phone_number", "address", "zipcode", "city"]
        for field in mandatory_fields:
            if not attrs.get(field):
                raise serializers.ValidationError({field: f"{field} is required."})

        return attrs

    def create(self, validated_data):
        """
        Create a new Landowner.
        """
        validated_data.pop("confirm_password")
        return Landowner.objects.create_user(**validated_data)


class ProjectDeveloperSerializer(serializers.ModelSerializer):
    """
    Serializer for ProjectDeveloper-specific profile details with embedded interest fields.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)
    wind = serializers.BooleanField(source="interest.wind", required=False)
    ground_mounted_solar = serializers.BooleanField(source="interest.ground_mounted_solar", required=False)
    battery = serializers.BooleanField(source="interest.battery", required=False)
    heat = serializers.BooleanField(source="interest.heat", required=False)
    hydrogen = serializers.BooleanField(source="interest.hydrogen", required=False)
    electromobility = serializers.BooleanField(source="interest.electromobility", required=False)
    ecological_upgrading = serializers.BooleanField(source="interest.ecological_upgrading", required=False)
    other = serializers.CharField(source="interest.other", required=False, allow_blank=True)

    class Meta:
        model = ProjectDeveloper
        fields = [
            "id",
            "profile_picture",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "address",
            "zipcode",
            "city",
            "company_name",
            "company_website",
            "company_logo",
            "founding_year",
            "mw_capacity",
            "employees",
            "position",
            "password",
            "confirm_password",
            "wind",
            "ground_mounted_solar",
            "battery",
            "heat",
            "hydrogen",
            "electromobility",
            "ecological_upgrading",
            "other",
            "role",
        ]
        read_only_fields = ["id", "email"]

    def validate(self, attrs):
        """
        Validate that passwords match and required fields are present.
        """
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError({"password": "Passwords do not match."})

        return attrs

    def create(self, validated_data):
        """
        Create a new ProjectDeveloper instance and associated ProjectDeveloperInterest.
        """
        # Extract interest-related fields
        interest_data = validated_data.pop("interest", {})

        # Create ProjectDeveloperInterest instance
        interest = ProjectDeveloperInterest.objects.create(**interest_data)

        # Remove confirm_password
        validated_data.pop("confirm_password")

        # Assign default subscription plan (Free Plan)
        if "tier" not in validated_data or not validated_data.get("tier"):
            from subscriptions.models import PlatformSubscription
            try:
                validated_data["tier"] = PlatformSubscription.objects.get(tier="FREE")
            except PlatformSubscription.DoesNotExist:
                raise serializers.ValidationError({"tier": "Default subscription plan (Free Plan) does not exist."})

        # Create ProjectDeveloper instance
        developer = ProjectDeveloper.objects.create_user(interest=interest, **validated_data)

        return developer

    def update(self, instance, validated_data):
        """
        Update the ProjectDeveloper instance and its associated interest fields.
        """
        # Extract and update interest fields if present
        interest_data = validated_data.pop("interest", {})
        for attr, value in interest_data.items():
            setattr(instance.interest, attr, value)
        instance.interest.save()

        # Update other fields on the ProjectDeveloper instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

class DeveloperDashboardSerializer(serializers.ModelSerializer):
    """
    Serializer for Project Developer dashboard data.

    Provides details about the developer's watchlist and active auctions.
    """

    watchlist = serializers.SerializerMethodField()
    auctions = serializers.SerializerMethodField()

    class Meta:
        model = ProjectDeveloper
        fields = ["id", "email", "watchlist", "auctions"]

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
