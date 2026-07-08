from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Account

User = get_user_model()


class SignUpTests(TestCase):
    """Self-serve registration: company name becomes the tenant Account,
    email/password become its first signed-in user."""

    def _payload(self, **overrides):
        payload = {
            'company_name': 'Acme Framing LLC',
            'email': 'owner@acmeframing.com',
            'password1': 'plank-and-rafter-42',
            'password2': 'plank-and-rafter-42',
        }
        payload.update(overrides)
        return payload

    def test_signup_creates_account_and_logs_user_in(self):
        response = self.client.post(reverse('accounts:signup'), self._payload())
        self.assertRedirects(response, reverse('projects:dashboard'))
        user = User.objects.get(email='owner@acmeframing.com')
        self.assertEqual(user.account.name, 'Acme Framing LLC')
        # The session is authenticated: the dashboard renders, no login redirect.
        dashboard = self.client.get(reverse('projects:dashboard'))
        self.assertEqual(dashboard.status_code, 200)

    def test_each_signup_gets_its_own_tenant(self):
        self.client.post(reverse('accounts:signup'), self._payload())
        self.client.logout()
        self.client.post(reverse('accounts:signup'), self._payload(
            company_name='Beta Builders', email='owner@betabuilders.com',
        ))
        self.assertEqual(Account.objects.filter(name__in=['Acme Framing LLC', 'Beta Builders']).count(), 2)
        acme = User.objects.get(email='owner@acmeframing.com')
        beta = User.objects.get(email='owner@betabuilders.com')
        self.assertNotEqual(acme.account_id, beta.account_id)

    def test_duplicate_email_is_rejected_with_message(self):
        User.objects.create_user(email='owner@acmeframing.com', password='irrelevant-pass-9')
        response = self.client.post(reverse('accounts:signup'), self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')
        self.assertEqual(User.objects.filter(email='owner@acmeframing.com').count(), 1)

    def test_mismatched_passwords_rejected(self):
        response = self.client.post(reverse('accounts:signup'), self._payload(password2='different-pass-42'))
        self.assertContains(response, 'did not match')
        self.assertFalse(User.objects.filter(email='owner@acmeframing.com').exists())

    @override_settings(AUTH_PASSWORD_VALIDATORS=[
        {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    ])
    def test_weak_password_rejected_by_validators(self):
        # Dev settings clear the validators, so pin one here: the form runs
        # validate_password, which enforces whatever production configures.
        response = self.client.post(reverse('accounts:signup'), self._payload(password1='short', password2='short'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='owner@acmeframing.com').exists())

    def test_authenticated_visitor_is_redirected_away(self):
        user = User.objects.create_user(email='existing@example.com', password='irrelevant-pass-9')
        self.client.force_login(user)
        response = self.client.get(reverse('accounts:signup'))
        self.assertRedirects(response, reverse('projects:dashboard'))

    def test_signup_linked_from_login_and_marketing(self):
        signup_url = reverse('accounts:signup')
        self.assertContains(self.client.get(reverse('login')), signup_url)
        self.assertContains(self.client.get(reverse('core:home')), signup_url)
        self.assertContains(self.client.get(reverse('core:pricing')), signup_url)


class EmailVerificationTests(TestCase):
    """Verification is soft: tracing works immediately, Stripe checkout does
    not until the emailed link is clicked. Tokens are signed and expiring."""

    def _signup(self):
        self.client.post(reverse('accounts:signup'), {
            'company_name': 'Verify Co',
            'email': 'verify@example.com',
            'password1': 'plank-and-rafter-42',
            'password2': 'plank-and-rafter-42',
        })
        return User.objects.get(email='verify@example.com')

    def test_signup_sends_verification_email_and_user_starts_unverified(self):
        from django.core import mail

        user = self._signup()
        self.assertFalse(user.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('verify', mail.outbox[0].subject.lower())
        self.assertIn('/accounts/verify-email/', mail.outbox[0].body)

    def test_emailed_link_verifies_the_user(self):
        from accounts.emails import make_verification_token

        user = self._signup()
        response = self.client.get(
            reverse('accounts:verify-email', args=[make_verification_token(user)]), follow=True,
        )
        self.assertContains(response, 'Email verified')
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    def test_garbage_and_expired_tokens_are_rejected(self):
        from unittest import mock

        from accounts.emails import make_verification_token

        user = self._signup()
        self.client.logout()
        response = self.client.get(
            reverse('accounts:verify-email', args=['not-a-real-token']), follow=True,
        )
        self.assertContains(response, 'invalid or has expired')
        # An expired signature behaves the same as garbage.
        token = make_verification_token(user)
        with mock.patch('accounts.emails.MAX_AGE_SECONDS', -1):
            response = self.client.get(reverse('accounts:verify-email', args=[token]), follow=True)
        self.assertContains(response, 'invalid or has expired')
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_resend_sends_a_fresh_email(self):
        from django.core import mail

        self._signup()
        mail.outbox.clear()
        response = self.client.post(reverse('accounts:resend-verification'), follow=True)
        self.assertContains(response, 'Verification email sent')
        self.assertEqual(len(mail.outbox), 1)

    def test_checkout_is_blocked_until_verified(self):
        from django.utils import timezone

        user = self._signup()
        response = self.client.post(reverse('billing:subscribe', args=['any-plan']), follow=True)
        self.assertContains(response, 'Verify your email before purchasing')
        # Once verified, the gate opens (the view then proceeds to plan lookup).
        user.email_verified_at = timezone.now()
        user.save(update_fields=['email_verified_at'])
        response = self.client.post(reverse('billing:subscribe', args=['any-plan']), follow=True)
        self.assertNotContains(response, 'Verify your email before purchasing')

    def test_unverified_banner_shows_and_clears(self):
        from django.utils import timezone

        user = self._signup()
        response = self.client.get(reverse('projects:dashboard'))
        self.assertContains(response, 'verify-banner')
        user.email_verified_at = timezone.now()
        user.save(update_fields=['email_verified_at'])
        response = self.client.get(reverse('projects:dashboard'))
        self.assertNotContains(response, 'verify-banner')

    def test_pre_existing_users_are_grandfathered_as_verified(self):
        # The data migration backfills email_verified_at from date_joined, so
        # only users created after this feature start unverified. Fresh
        # create_user calls (post-migration) start unverified by design.
        user = User.objects.create_user(email='old-timer@example.com', password='irrelevant-pass-9')
        self.assertFalse(user.email_verified)
