from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    account = models.ForeignKey(
        'accounts.Account', on_delete=models.PROTECT, related_name='users',
    )
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    email_verified_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When the user confirmed this address via the emailed link. '
                  'Signing in never requires it; Stripe checkout does.',
    )
    keep_tool_active_after_draw = models.BooleanField(
        default=True,
        help_text='When enabled, the plan viewer keeps the current drawing tool armed until Escape is pressed.',
    )

    objects = UserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    @property
    def email_verified(self):
        return self.email_verified_at is not None

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name

    def __str__(self):
        return self.email
