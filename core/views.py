from django.shortcuts import redirect
from django.views.generic import TemplateView

from billing.services import estimate_unlock_offer, subscription_plans


class HomeView(TemplateView):
    """Marketing landing page. Signed-in users skip straight to their work:
    the dashboard is home once you have an account."""

    template_name = 'core/home.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('projects:dashboard')
        return super().get(request, *args, **kwargs)


class PricingView(TemplateView):
    """Public pricing page. Plans and the single-estimate unlock come from the
    same billing settings checkout uses, so marketing copy can never drift
    from what Stripe actually charges."""

    template_name = 'core/pricing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plans'] = subscription_plans()
        context['unlock'] = estimate_unlock_offer()
        return context
