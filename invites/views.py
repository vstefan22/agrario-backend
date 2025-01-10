from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import InviteLink, PromoCode
from accounts.models import MarketUser
from .serializers import InviteLinkSerializer, PromoCodeSerializer
import uuid
from django.core.mail import send_mail
from django.conf import settings


class CreateInviteLinkView(APIView):
    """
    API view to create an invite link and send it via email.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        invite_email = request.data.get("email")

        if not invite_email:
            return Response({"error": "Invite email is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Create invite link
        invite = InviteLink.objects.create(
            created_by=user,
            uri_hash=uuid.uuid4().hex[:16],
            is_active=True
        )

        # Generate invitation link
        invitation_link = f"{settings.FRONTEND_URL}/register?invite_code={invite.uri_hash}"

        # Send the invitation email
        try:
            send_mail(
                subject="You're Invited to Join Agrario!",
                message=f"Hi, you've been invited to join Agrario. Click the link below to register:\n\n{invitation_link}",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[invite_email],
                fail_silently=False,
            )
        except Exception as e:
            return Response({"error": "Failed to send invitation email."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": "Invitation link sent successfully."}, status=status.HTTP_201_CREATED)

class ValidateInviteLinkView(APIView):
    """
    API view to validate an invite link.
    """
    def get(self, request, code):
        try:
            invite = InviteLink.objects.get(uri_hash=code, is_active=True)
            return Response({"message": "Invite is valid."}, status=status.HTTP_200_OK)
        except InviteLink.DoesNotExist:
            return Response({"error": "Invalid or expired invite link."}, status=status.HTTP_400_BAD_REQUEST)


from django.db import IntegrityError

class RegisterWithInviteView(APIView):
    """
    API view to register a user with an invite code and generate a promo code for the inviter.
    """

    def post(self, request):
        invite_code = request.data.get("invite_code")
        user_data = request.data.get("user_data")

        # Validate password confirmation
        if user_data.get("password") != user_data.pop("confirm_password", None):
            return Response({"error": "Password confirmation does not match."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Check invite validity
            invite = InviteLink.objects.get(uri_hash=invite_code, is_active=True)

            # Create the user
            try:
                user = MarketUser.objects.create_user(
                    email=user_data["email"],
                    password=user_data["password"],
                    role=user_data["role"],
                    phone_number=user_data.get("phone_number"),
                    address=user_data.get("address"),
                    company_name=user_data.get("company_name"),
                    company_website=user_data.get("company_website"),
                    profile_picture=user_data.get("profile_picture"),
                    zipcode=user_data.get("zipcode"),
                    city=user_data.get("city"),
                    street_housenumber=user_data.get("street_housenumber"),
                )
            except IntegrityError as e:
                if "accounts_marketuser_email_key" in str(e):
                    return Response({"error": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)
                raise e  # Re-raise other integrity errors

            # Mark invite as used
            invite.is_active = False
            invite.successful_referrals += 1
            invite.save()

            # Generate promo code for inviter
            promo_code = PromoCode.objects.create(
                created_by=invite.created_by,
                code=str(uuid.uuid4().hex[:8]).upper(),
                amount_percent=10,
                is_active=True
            )
            self.send_promo_code_email(invite.created_by, promo_code.code)

            return Response({"message": "User registered successfully.", "promo_code": promo_code.code}, status=status.HTTP_201_CREATED)

        except InviteLink.DoesNotExist:
            return Response({"error": "Invalid or expired invite code."}, status=status.HTTP_400_BAD_REQUEST)

        except IntegrityError as e:
            return Response({"error": "An unexpected database error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def send_promo_code_email(self, user, promo_code):
        """
        Sends the promo code to the inviter via email.
        """
        try:
            send_mail(
                subject="Your Promo Code from Agrario",
                message=f"Hi {user.first_name},\n\nThank you for inviting a new user! Here is your promo code: {promo_code}.\n\nYou can redeem this code in your account.\n\nBest regards,\nThe Agrario Team",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            # Log or handle the exception
            print(f"Failed to send promo code email to {user.email}: {str(e)}")




class RedeemPromoCodeView(APIView):
    """
    API view for redeeming promo codes.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code")
        try:
            promo = PromoCode.objects.get(code=code, is_active=True, assigned_to=request.user)
            promo.is_active = False
            promo.redeemed_by = request.user
            promo.save()
            return Response({"message": f"Promo code {promo.code} redeemed successfully."})
        except PromoCode.DoesNotExist:
            return Response({"error": "Invalid or inactive promo code."}, status=status.HTTP_400_BAD_REQUEST)
