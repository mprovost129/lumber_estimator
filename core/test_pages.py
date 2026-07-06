from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()

TEST_PLANS = [
    {
        'slug': 'starter', 'name': 'Starter', 'price_label': '$29 / month',
        'description': 'Starter plan.', 'price_id': 'price_starter_test',
    },
    {
        'slug': 'pro', 'name': 'Pro', 'price_label': '$79 / month',
        'description': 'Pro plan.', 'price_id': '',
    },
]


class HomePageTests(TestCase):
    def test_anonymous_visitor_gets_marketing_page(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mkt-hero')
        self.assertContains(response, 'Start a takeoff')
        self.assertContains(response, reverse('core:pricing'))

    def test_authenticated_user_is_redirected_to_dashboard(self):
        user = User.objects.create_user(email='home@example.com', password='testpass123')
        self.client.force_login(user)
        response = self.client.get(reverse('core:home'))
        self.assertRedirects(response, reverse('projects:dashboard'))


@override_settings(BILLING_SUBSCRIPTION_PLANS=TEST_PLANS)
class PricingPageTests(TestCase):
    def test_pricing_is_public_and_lists_configured_plans(self):
        response = self.client.get(reverse('core:pricing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Starter')
        self.assertContains(response, '$29 / month')
        self.assertContains(response, 'Pro')
        # Anonymous visitors are sent to sign in, not to checkout.
        self.assertContains(response, 'Sign in to subscribe')

    def test_signed_in_user_gets_subscribe_forms(self):
        user = User.objects.create_user(email='pricing@example.com', password='testpass123')
        self.client.force_login(user)
        response = self.client.get(reverse('core:pricing'))
        self.assertContains(response, reverse('billing:subscribe', args=['starter']))
        # A plan with no configured Stripe price renders its button disabled.
        self.assertContains(response, 'disabled title="Checkout is not configured yet"')
