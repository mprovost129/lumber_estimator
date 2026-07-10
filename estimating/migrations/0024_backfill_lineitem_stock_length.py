from decimal import Decimal

from django.db import migrations


def backfill_stock_length(apps, schema_editor):
    LineItem = apps.get_model('estimating', 'LineItem')
    MaterialLength = apps.get_model('catalog', 'MaterialLength')

    lengths_by_product = {}
    for length in MaterialLength.objects.all():
        key = (length.product_id, Decimal(str(length.length_ft)).quantize(Decimal('0.01')))
        lengths_by_product[key] = length.id

    for item in LineItem.objects.filter(stock_length__isnull=True, length_ft__isnull=False):
        key = (item.material_id, Decimal(str(item.length_ft)).quantize(Decimal('0.01')))
        match_id = lengths_by_product.get(key)
        if match_id is not None:
            item.stock_length_id = match_id
            item.save(update_fields=['stock_length'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0023_calculationrule_preferred_length_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_stock_length, noop),
    ]
