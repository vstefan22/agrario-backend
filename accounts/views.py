from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import MarketUser, InviteLink
from .serializers import UserRegistrationSerializer, UserSerializer
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_decode
from rest_framework.views import APIView
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import authenticate, login
from rest_framework.authtoken.models import Token

class MarketUserViewSet(viewsets.ModelViewSet):
    queryset = MarketUser.objects.all()
    serializer_class = UserRegistrationSerializer

    def get_permissions(self):
        """
        Override permissions for specific actions.
        """
        if self.action in ['create', 'dashboard']:
            if self.action == 'create':
                return [AllowAny()]
            return [IsAuthenticated()]  # Auth required for dashboard
        return [IsAuthenticated()]  # Default for other actions

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Send confirmation email
        serializer.send_confirmation_email(user)

        return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def generate_invite_link(self, request, pk=None):
        user = self.get_object()
        invite_link, created = InviteLink.objects.get_or_create(created_by=user, is_active=True)
        invitation_code = invite_link.uri_hash
        invitation_link = f"http://localhost:8000/register?invite_code={invitation_code}"

        # Send invite link via email
        send_mail(
            subject="Your Invitation Link",
            message=f"Hi {user.username},\n\nHere is your invite link:\n{invitation_link}",
            from_email="noreply@example.com",
            recipient_list=[user.email],
        )
        return Response({
            "invite_code": invitation_code,
            "invitation_link": invitation_link,
            "message": "Invite link generated and sent via email."
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def dashboard(self, request):
        """
        Custom action to fetch dashboard details for the authenticated user.
        """
        user = request.user  # Get the authenticated user
        user_data = UserSerializer(user).data  # Serialize user details

        # Example: Add additional dashboard-specific data
        dashboard_data = {
            "user_info": user_data,
            "dashboard_greeting": f"Welcome to your dashboard, {user.username}!",
            "important_links": [
                {"name": "Profile", "url": "/profile"},
                {"name": "Settings", "url": "/settings"},
                {"name": "Logout", "url": "/logout"},
            ],
        }

        return Response(dashboard_data)


class ConfirmEmailView(APIView):
    permission_classes = [AllowAny]  # Allow anyone to access this endpoint

    def get(self, request, uidb64, token):
        try:
            # Decode the user ID from the URL
            uid = urlsafe_base64_decode(uidb64).decode()
            user = MarketUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, MarketUser.DoesNotExist):
            return Response({"error": "Invalid or expired confirmation link."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate the token
        if default_token_generator.check_token(user, token):
            if user.is_email_confirmed:
                return Response({"message": "Your email is already confirmed. You can log in now."},
                                status=status.HTTP_200_OK)

            # Confirm the email
            user.is_email_confirmed = True
            user.save()
            return Response({"message": "Your account has been confirmed successfully. You can log in now."},
                            status=status.HTTP_200_OK)

        # If the token is invalid
        return Response({"error": "Invalid or expired confirmation link."}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    Login with email and password, ensuring email confirmation is checked.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch user by email
            user = MarketUser.objects.get(email=email)
        except MarketUser.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        # Validate the password
        if not user.check_password(password):
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        # Check if email is confirmed
        if not user.is_email_confirmed:
            return Response({'error': 'Please confirm your email before logging in.'}, status=status.HTTP_403_FORBIDDEN)

        # Generate or retrieve the token
        try:
            token, _ = Token.objects.get_or_create(user=user)
        except Exception as e:
            return Response({'error': f'Failed to create token: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Serialize user data
        user_data = UserSerializer(user).data
        return Response({'token': token.key, 'user': user_data}, status=status.HTTP_200_OK)
