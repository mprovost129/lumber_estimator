from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0012_materialproduct_supported_input_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='materialproduct',
            name='quantity_per_box',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Used whenever Box is one of the supported input types, e.g. 100 screws per box.',
                null=True,
            ),
        ),
    ]
