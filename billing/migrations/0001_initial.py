from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0002_add_layout_preferences'),
        ('projects', '0005_projecttemplate_is_favorite'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StripeWebhookEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.CharField(max_length=255, unique=True)),
                ('event_type', models.CharField(max_length=100)),
                ('processed_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='AccountBillingProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_customer_id', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='billing_profile', to='accounts.account')),
            ],
        ),
        migrations.CreateModel(
            name='AccountSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_subscription_id', models.CharField(max_length=255, unique=True)),
                ('plan_slug', models.CharField(max_length=50)),
                ('status', models.CharField(choices=[('incomplete', 'Incomplete'), ('trialing', 'Trialing'), ('active', 'Active'), ('past_due', 'Past due'), ('canceled', 'Canceled'), ('unpaid', 'Unpaid'), ('incomplete_expired', 'Incomplete expired')], default='incomplete', max_length=30)),
                ('current_period_end', models.DateTimeField(blank=True, null=True)),
                ('cancel_at_period_end', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to='accounts.account')),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.CreateModel(
            name='EstimateAccessGrant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('single_use', 'Single use')], default='single_use', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('refunded', 'Refunded'), ('void', 'Void')], default='pending', max_length=20)),
                ('stripe_checkout_session_id', models.CharField(blank=True, max_length=255)),
                ('stripe_payment_intent_id', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('estimate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_grants', to='projects.estimate')),
                ('purchased_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='estimate_access_grants', to='users.user')),
            ],
            options={'ordering': ['-updated_at']},
        ),
    ]
