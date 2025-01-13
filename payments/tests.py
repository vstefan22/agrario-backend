from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch
from django.utils.timezone import now, timedelta
from accounts.models import ProjectDeveloper, ProjectDeveloperInterest
from subscriptions.models import PlatformSubscription, ProjectDeveloperSubscription
from reports.models import Parcel
from payments.models import PaymentTransaction

class ProjectDeveloperSubscriptionTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test interest
        self.interest = ProjectDeveloperInterest.objects.create(
            wind=True,
            ground_mounted_solar=False,
            battery=True,
            heat=False,
            hydrogen=False,
            electromobility=False,
            ecological_upgrading=False,
            other="Custom Interest",
        )

        self.plan = PlatformSubscription.objects.create(
            title="Free Plan",
            description="Default free plan for project developers",
            tier="FREE",
            valid_from=now().date(),  # Ensure valid_from is not null
            valid_to=now().date() + timedelta(days=365),
            amount_paid_per_month=0.00,
        )

        # Create test user
        self.user = ProjectDeveloper.objects.create_user(
            email="developer@example.com",
            password="password123",
            role="developer",
            interest=self.interest,
            tier=self.plan
        )
        self.client.force_authenticate(user=self.user)

        # Create test subscription plan
        self.plan = PlatformSubscription.objects.create(
            title="Premium Plan",
            description="Premium subscription for project developers",
            tier="PREM",
            valid_from=now().date(),  # Ensure valid_from is not null
            valid_to=now().date() + timedelta(days=365),
            amount_paid_per_month=100.00,
        )

        # Create test parcel
        self.parcel = Parcel.objects.create(
            id=1,
            created_by=self.user,
            area_square_meters=100,
            status="available",
        )

    @patch("stripe.PaymentIntent.create")
    def test_subscription_upgrade_payment(self, mock_stripe_intent):
        """Test upgrading a developer's subscription using Stripe."""
        # Mock Stripe response
        mock_stripe_intent.return_value = {
            "id": "pi_12345",
            "client_secret": "test_secret",
        }

        response = self.client.post(
            "/api/payments/create-payment/",
            {
                "plan_id": self.plan.id,
                "currency": "usd",
                "payment_method": "card",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("client_secret", response.data)

        # Ensure subscription is created
        self.assertTrue(
            ProjectDeveloperSubscription.objects.filter(
                by_user=self.user, tier=self.plan
            ).exists()
        )

    @patch("stripe.PaymentIntent.create")
    def test_analyse_plus_payment(self, mock_stripe_intent):
        """Test purchasing Analyse Plus for parcels."""
        # Mock Stripe response
        mock_stripe_intent.return_value = {
            "id": "pi_67890",
            "client_secret": "test_secret",
        }

        response = self.client.post(
            "/api/payments/create-payment/",
            {
                "parcel_ids": [self.parcel.id],
                "currency": "usd",
                "payment_method": "card",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("client_secret", response.data)

    def test_duplicate_subscription(self):
        """Test attempting to subscribe to a plan already active."""
        ProjectDeveloperSubscription.objects.create(
            by_user=self.user,
            tier=self.plan,
            valid_from=now().date(),
            valid_to=now().date() + timedelta(days=30),
        )

        response = self.client.post(
            "/api/payments/create-payment/",
            {
                "plan_id": self.plan.id,
                "currency": "usd",
                "payment_method": "card",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)
        self.assertIn("already subscribed", response.data["error"].lower())

    def test_invalid_plan_id(self):
        """Test subscription with an invalid plan ID."""
        response = self.client.post(
            "/api/payments/create-payment/",
            {
                "plan_id": 9999,  # Non-existent plan ID
                "currency": "usd",
                "payment_method": "card",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid plan ID.", response.data["error"])

    def test_invalid_parcel_ids(self):
        """Test Analyse Plus purchase with invalid parcel IDs."""
        response = self.client.post(
            "/api/payments/create-payment/",
            {
                "parcel_ids": [9999],  # Non-existent parcel ID
                "currency": "usd",
                "payment_method": "card",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No valid parcels found.", response.data["error"])
