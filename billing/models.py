from django.db import models


class AccountBillingProfile(models.Model):
    account = models.OneToOneField(
        'accounts.Account', on_delete=models.CASCADE, related_name='billing_profile',
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Billing profile for {self.account.name}'


class AccountSubscription(models.Model):
    class Status(models.TextChoices):
        INCOMPLETE = 'incomplete', 'Incomplete'
        TRIALING = 'trialing', 'Trialing'
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Past due'
        CANCELED = 'canceled', 'Canceled'
        UNPAID = 'unpaid', 'Unpaid'
        INCOMPLETE_EXPIRED = 'incomplete_expired', 'Incomplete expired'

    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE, related_name='subscriptions',
    )
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    plan_slug = models.CharField(max_length=50)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.INCOMPLETE)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.account.name} {self.plan_slug} subscription'


class EstimateAccessGrant(models.Model):
    class Kind(models.TextChoices):
        SINGLE_USE = 'single_use', 'Single use'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        REFUNDED = 'refunded', 'Refunded'
        VOID = 'void', 'Void'

    estimate = models.ForeignKey(
        'projects.Estimate', on_delete=models.CASCADE, related_name='access_grants',
    )
    purchased_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='estimate_access_grants',
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SINGLE_USE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Access grant for estimate {self.estimate_id}'


class StripeWebhookEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_id

