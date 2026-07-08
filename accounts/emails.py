from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

# Stateless tokens: the user id signed with a timestamp, so no token table and
# nothing to clean up. Links expire after MAX_AGE_SECONDS; a fresh one can be
# requested from the banner at any time.
SIGNING_SALT = 'accounts.email-verification'
MAX_AGE_SECONDS = 3 * 24 * 60 * 60


def make_verification_token(user):
    return signing.dumps({'user_id': user.pk}, salt=SIGNING_SALT)


def read_verification_token(token):
    """Returns the user id, or None for garbage, tampered, or expired tokens."""
    try:
        payload = signing.loads(token, salt=SIGNING_SALT, max_age=MAX_AGE_SECONDS)
        return payload.get('user_id')
    except (signing.BadSignature, signing.SignatureExpired):
        return None


def send_verification_email(request, user):
    verify_url = request.build_absolute_uri(
        reverse('accounts:verify-email', args=[make_verification_token(user)])
    )
    send_mail(
        subject='Verify your Lumber Estimator email',
        message=(
            'Welcome to Lumber Estimator!\n\n'
            'Confirm this email address by opening the link below. The link is good for 3 days.\n\n'
            f'{verify_url}\n\n'
            'You can trace plans and build material lists right away; a verified email is only '
            'needed before purchasing an export or subscription.\n\n'
            'If you did not create this account, you can ignore this message.'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=[user.email],
        fail_silently=False,
    )
