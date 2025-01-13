from django.core.management.base import BaseCommand
from subscriptions.models import PlatformSubscription
from datetime import date

class Command(BaseCommand):
    help = "Preload default subscription plans (Free, Premium, Enterprise)."

    def handle(self, *args, **kwargs):
        plans = [
            {
                "tier": PlatformSubscription.SubscriptionTier.FREE,
                "title": "Free Plan",
                "description": "Default free subscription plan for project developers.",
                "valid_from": date.today(),
                "valid_to": "9999-01-01",
                "amount_paid_per_month": 0.00,
            },
            {
                "tier": PlatformSubscription.SubscriptionTier.PREMIUM,
                "title": "Premium Plan",
                "description": "Premium subscription plan with additional features.",
                "valid_from": date.today(),
                "valid_to": "9999-01-01",
                "amount_paid_per_month": 100.00,
            },
            {
                "tier": PlatformSubscription.SubscriptionTier.ENTERPRISE,
                "title": "Enterprise Plan",
                "description": "Enterprise subscription plan with full access.",
                "valid_from": date.today(),
                "valid_to": "9999-01-01",
                "amount_paid_per_month": 500.00,
            },
        ]

        for plan in plans:
            subscription, created = PlatformSubscription.objects.get_or_create(
                tier=plan["tier"],
                defaults=plan,
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Subscription plan '{subscription.title}' created.")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Subscription plan '{subscription.title}' already exists.")
                )

        self.stdout.write(self.style.SUCCESS("Subscription plans populated successfully!"))
