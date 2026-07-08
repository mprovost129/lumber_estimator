from django.db import migrations
from django.db.models import F


def grandfather_existing_users(apps, schema_editor):
    """Users created before verification existed (including the operator)
    should not be nagged or blocked from checkout: treat their signup date as
    the verification date. New signups start unverified."""
    User = apps.get_model('users', 'User')
    User.objects.filter(email_verified_at__isnull=True).update(email_verified_at=F('date_joined'))


def unverify_everyone(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.update(email_verified_at=None)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_email_verified_at'),
    ]

    operations = [
        migrations.RunPython(grandfather_existing_users, unverify_everyone),
    ]
