from django.db import migrations, models


def backfill_supported_input_types(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    for product in MaterialProduct.objects.all():
        input_type = getattr(product, 'input_type', None) or 'each'
        product.supported_input_types = [input_type]
        product.save(update_fields=['supported_input_types'])


def revert_supported_input_types(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    MaterialProduct.objects.update(supported_input_types=[])


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0011_seed_brand_connectors'),
    ]

    operations = [
        migrations.AddField(
            model_name='materialproduct',
            name='supported_input_types',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='One or more ordering methods this material supports, e.g. feet stock, per-piece, or box.',
            ),
        ),
        migrations.RunPython(backfill_supported_input_types, revert_supported_input_types),
    ]
