from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from projects.models import Estimate

from .models import StripeWebhookEvent
from .services import (
    billing_enabled,
    create_customer_portal_session,
    create_estimate_checkout_session,
    create_subscription_checkout_session,
    estimate_output_access,
    estimate_unlock_offer,
    mark_estimate_checkout_paid,
    stripe_module,
    subscription_plan_by_slug,
    subscription_plans,
    sync_subscription_from_payload,
)


class BillingOverviewView(LoginRequiredMixin, View):
    def get(self, request):
        estimates = (
            Estimate.objects.for_account(request.user.account)
            .select_related('project')
            .order_by('-created_at')[:10]
        )
        estimate_rows = [
            {'estimate': estimate, 'access': estimate_output_access(estimate)}
            for estimate in estimates
        ]
        return render(request, 'billing/overview.html', {
            'billing_enabled': billing_enabled(),
            'estimate_unlock_offer': estimate_unlock_offer(),
            'plans': subscription_plans(),
            'estimate_rows': estimate_rows,
        })


class EstimateCheckoutSessionCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        estimate = get_object_or_404(
            Estimate.objects.for_account(request.user.account).select_related('project'),
            pk=pk,
        )
        try:
            session = create_estimate_checkout_session(request, estimate)
        except ImproperlyConfigured as exc:
            messages.error(request, str(exc))
            return redirect('billing:overview')
        return redirect(session['url'])


class SubscriptionCheckoutSessionCreateView(LoginRequiredMixin, View):
    def post(self, request, slug):
        plan = subscription_plan_by_slug(slug)
        try:
            session = create_subscription_checkout_session(request, plan)
        except ImproperlyConfigured as exc:
            messages.error(request, str(exc))
            return redirect('billing:overview')
        return redirect(session['url'])


class CustomerPortalLaunchView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            session = create_customer_portal_session(request.user.account)
        except ImproperlyConfigured as exc:
            messages.error(request, str(exc))
            return redirect('billing:overview')
        return redirect(session['url'])


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    def post(self, request):
        payload = request.body
        signature = request.headers.get('Stripe-Signature', '')
        secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        if not secret:
            return HttpResponseBadRequest('Webhook secret not configured.')
        stripe = stripe_module()
        try:
            event = stripe.Webhook.construct_event(payload, signature, secret)
        except ValueError:
            return HttpResponseBadRequest('Invalid payload.')
        except stripe.error.SignatureVerificationError:
            return HttpResponseBadRequest('Invalid signature.')

        if StripeWebhookEvent.objects.filter(event_id=event['id']).exists():
            return HttpResponse(status=200)

        data = event['data']['object']
        if event['type'] == 'checkout.session.completed':
            mark_estimate_checkout_paid(data)
        elif event['type'] in {
            'customer.subscription.created',
            'customer.subscription.updated',
            'customer.subscription.deleted',
        }:
            sync_subscription_from_payload(data)

        StripeWebhookEvent.objects.create(event_id=event['id'], event_type=event['type'])
        return HttpResponse(status=200)
