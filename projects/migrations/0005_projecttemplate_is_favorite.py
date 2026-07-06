from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0004_project_templates_and_decimal_heights'),
    ]

    operations = [
        migrations.AddField(
            model_name='projecttemplate',
            name='is_favorite',
            field=models.BooleanField(
                default=False,
                help_text='Shown first in the New Project flow and template library for this account.',
            ),
        ),
    ]
