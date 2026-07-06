from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import AccountBillingProfile, AccountSubscription, EstimateAccessGrant

ACTIVE_SUBSCRIPTION_STATUSES = {
    AccountSubscription.Status.TRIALING,
    AccountSubscription.Status.ACTIVE,
    AccountSubscription.Status.PAST_DUE,
}


@dataclass(frozen=True)
class BillingPlan:
    slug: str
    name: str
    price_label: str
    description: str
    price_id: str

    @property
    def enabled(self):
        return bool(self.price_id)


def subscription_plans():
    configured = getattr(settings, 'BILLING_SUBSCRIPTION_PLANS', [])
    return [BillingPlan(**plan) for plan in configured]


def subscription_plan_by_slug(slug):
    return next((plan for plan in subscription_plans() if plan.slug == slug), None)


def subscription_plan_by_price_id(price_id):
    return next((plan for plan in subscription_plans() if plan.price_id == price_id), None)


def estimate_unlock_offer():
    return getattr(settings, 'BILLING_ESTIMATE_UNLOCK', {})


def billing_enabled():
    offer = estimate_unlock_offer()
    return bool(
        getattr(settings, 'STRIPE_SECRET_KEY', '')
        and getattr(settings, 'APP_BASE_URL', '')
        and (offer.get('price_id') or any(plan.enabled for plan in subscription_plans()))
    )


def active_subscription_for(account):
    return (
        AccountSubscription.objects.filter(
            account=account,
            status__in=ACTIVE_SUBSCRIPTION_STATUSES,
        )
        .order_by('-updated_at')
        .first()
    )


def estimate_has_paid_access(estimate):
    return EstimateAccessGrant.objects.filter(
        estimate=estimate,
        status=EstimateAccessGrant.Status.PAID,
    ).exists()


def estimate_output_access(estimate):
    subscription = active_subscription_for(estimate.project.account)
    if subscription is not None:
        plan = subscription_plan_by_slug(subscription.plan_slug)
        return {
            'can_access': True,
            'source': 'subscription',
            'subscription': subscription,
            'plan': plan,
            'label': plan.name if plan else subscription.plan_slug.replace('_', ' ').title(),
        }
    if estimate_has_paid_access(estimate):
        return {
            'can_access': True,
            'source': 'single_use',
            'subscription': None,
            'plan': None,
            'label': 'Single estimate unlock',
        }
    return {
        'can_access': False,
        'source': 'locked',
        'subscription': None,
        'plan': None,
        'label': '',
    }


def get_or_create_billing_profile(account):
    return AccountBillingProfile.objects.get_or_create(account=account)[0]


def stripe_module():
    try:
        import stripe
    except ImportError as exc:
        raise ImproperlyConfigured('Install the stripe package to use billing checkout.') from exc
    secret = getattr(settings, 'STRIPE_SECRET_KEY', '')
    if not secret:
        raise ImproperlyConfigured('Set STRIPE_SECRET_KEY to use billing checkout.')
    stripe.api_key = secret
    return stripe


def build_absolute_url(path):
    base_url = getattr(settings, 'APP_BASE_URL', '').rstrip('/')
    if not base_url:
        raise ImproperlyConfigured('Set APP_BASE_URL to your public site URL.')
    return f'{base_url}{path}'


def ensure_stripe_customer(account, email):
    profile = get_or_create_billing_profile(account)
    if profile.stripe_customer_id:
        return profile.stripe_customer_id
    stripe = stripe_module()
    customer = stripe.Customer.create(
        email=email,
        name=account.name,
        metadata={'account_id': str(account.pk)},
    )
    profile.stripe_customer_id = customer['id']
    profile.save(update_fields=['stripe_customer_id', 'updated_at'])
    return profile.stripe_customer_id


def create_estimate_checkout_session(request, estimate):
    offer = estimate_unlock_offer()
    price_id = offer.get('price_id')
    if not price_id:
        raise ImproperlyConfigured('Set BILLING_ESTIMATE_UNLOCK.price_id before enabling estimate unlock checkout.')
    stripe = stripe_module()
    customer_id = ensure_stripe_customer(request.user.account, request.user.email)
    session = stripe.checkout.Session.create(
        mode='payment',
        customer=customer_id,
        client_reference_id=str(estimate.pk),
        line_items=[{'price': price_id, 'quantity': 1}],
        success_url=build_absolute_url(estimate.get_absolute_url()) + '?billing=success',
        cancel_url=build_absolute_url(estimate.get_absolute_url()) + '?billing=cancelled',
        metadata={
            'kind': 'estimate_unlock',
            'account_id': str(request.user.account_id),
            'estimate_id': str(estimate.pk),
            'user_id': str(request.user.pk),
        },
        allow_promotion_codes=True,
    )
    EstimateAccessGrant.objects.get_or_create(
        estimate=estimate,
        stripe_checkout_session_id=session['id'],
        defaults={
            'purchased_by': request.user,
            'status': EstimateAccessGrant.Status.PENDING,
        },
    )
    return session


def create_subscription_checkout_session(request, plan):
    if not plan or not plan.price_id:
        raise ImproperlyConfigured('This subscription plan is not configured with a Stripe price ID.')
    stripe = stripe_module()
    customer_id = ensure_stripe_customer(request.user.account, request.user.email)
    session = stripe.checkout.Session.create(
        mode='subscription',
        customer=customer_id,
        line_items=[{'price': plan.price_id, 'quantity': 1}],
        success_url=build_absolute_url('/billing/') + '?billing=success',
        cancel_url=build_absolute_url('/billing/') + '?billing=cancelled',
        metadata={
            'kind': 'subscription',
            'account_id': str(request.user.account_id),
            'plan_slug': plan.slug,
            'user_id': str(request.user.pk),
        },
        subscription_data={
            'metadata': {
                'account_id': str(request.user.account_id),
                'plan_slug': plan.slug,
            }
        },
        allow_promotion_codes=True,
    )
    return session


def create_customer_portal_session(account):
    profile = get_or_create_billing_profile(account)
    if not profile.stripe_customer_id:
        raise ImproperlyConfigured('No Stripe customer exists for this account yet.')
    stripe = stripe_module()
    return stripe.billing_portal.Session.create(
        customer=profile.stripe_customer_id,
        return_url=build_absolute_url('/billing/'),
    )


def sync_subscription_from_payload(payload):
    subscription_id = payload.get('id')
    metadata = payload.get('metadata') or {}
    account_id = metadata.get('account_id')
    if not subscription_id or not account_id:
        return None
    items = (((payload.get('items') or {}).get('data')) or [])
    price_id = ''
    if items:
        price_id = (((items[0] or {}).get('price')) or {}).get('id', '')
    plan = subscription_plan_by_slug(metadata.get('plan_slug')) or subscription_plan_by_price_id(price_id)
    current_period_end = payload.get('current_period_end')
    if current_period_end:
        current_period_end = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
    subscription, _ = AccountSubscription.objects.update_or_create(
        stripe_subscription_id=subscription_id,
        defaults={
            'account_id': account_id,
            'plan_slug': plan.slug if plan else metadata.get('plan_slug', 'starter'),
            'status': payload.get('status', AccountSubscription.Status.INCOMPLETE),
            'current_period_end': current_period_end,
            'cancel_at_period_end': bool(payload.get('cancel_at_period_end')),
        },
    )
    return subscription


def mark_estimate_checkout_paid(payload):
    metadata = payload.get('metadata') or {}
    if metadata.get('kind') != 'estimate_unlock' or payload.get('payment_status') != 'paid':
        return None
    estimate_id = metadata.get('estimate_id') or payload.get('client_reference_id')
    if not estimate_id:
        return None
    grant, _ = EstimateAccessGrant.objects.update_or_create(
        stripe_checkout_session_id=payload.get('id', ''),
        defaults={
            'estimate_id': estimate_id,
            'purchased_by_id': metadata.get('user_id'),
            'status': EstimateAccessGrant.Status.PAID,
            'stripe_payment_intent_id': payload.get('payment_intent', '') or '',
        },
    )
    return grant
