from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from .emails import read_verification_token, send_verification_email
from .forms import SignUpForm

User = get_user_model()


class SignUpView(View):
    """Self-serve registration for the public marketing funnel. Creates the
    Account (tenant) and its first user, signs them in, and lands them on the
    dashboard ready to start a takeoff. A verification email goes out at the
    same time; verifying is only required before Stripe checkout, so the
    time-to-first-takeoff stays friction-free."""

    template_name = 'registration/signup.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('projects:dashboard')
        return render(request, self.template_name, {'form': SignUpForm()})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('projects:dashboard')
        form = SignUpForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        user = form.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        send_verification_email(request, user)
        messages.success(
            request,
            'Welcome! Create your first project to start a takeoff. '
            'We also sent a link to verify your email.',
        )
        return redirect('projects:dashboard')


class VerifyEmailView(View):
    """Landing for the emailed link. Login is not required: the link may be
    opened in a different browser than the signup session. The token alone
    proves control of the inbox."""

    def get(self, request, token):
        user_id = read_verification_token(token)
        user = User.objects.filter(pk=user_id).first() if user_id else None
        if user is None:
            messages.error(
                request,
                'That verification link is invalid or has expired. '
                'Log in and use "Resend verification email" to get a fresh one.',
            )
            return redirect('login')
        if not user.email_verified:
            user.email_verified_at = timezone.now()
            user.save(update_fields=['email_verified_at'])
        messages.success(request, 'Email verified. You are all set.')
        return redirect('projects:dashboard' if request.user.is_authenticated else 'login')


class ResendVerificationView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.email_verified:
            messages.info(request, 'Your email is already verified.')
        else:
            send_verification_email(request, request.user)
            messages.success(request, f'Verification email sent to {request.user.email}.')
        return redirect(request.META.get('HTTP_REFERER') or 'projects:dashboard')
