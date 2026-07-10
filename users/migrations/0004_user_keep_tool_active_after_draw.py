from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_grandfather_email_verification'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='keep_tool_active_after_draw',
            field=models.BooleanField(
                default=True,
                help_text='When enabled, the plan viewer keeps the current drawing tool armed until Escape is pressed.',
            ),
        ),
    ]
