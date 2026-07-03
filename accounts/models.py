from django.db import models


class Account(models.Model):
    """The tenant. Every Project, Estimate, and PriceEntry belongs to one Account."""

    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class AccountScopedManager(models.Manager):
    """Base manager for tenant-owned models. Views must use `for_account()`,
    never the bare `.objects.all()`, so tenant isolation can't be forgotten."""

    def for_account(self, account):
        return self.get_queryset().filter(account=account)
