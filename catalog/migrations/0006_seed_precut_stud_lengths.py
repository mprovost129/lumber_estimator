from decimal import Decimal

from django.db import migrations

# Standard precut stud lengths: 92-5/8 in (for an 8'-1-1/8" assembled wall
# with a single bottom plate + double top plate) and 104-5/8 in (for a
# 9'-1-1/8" wall) - stored in feet since MaterialLength.length_ft is the
# canonical unit throughout, but exact: 92.625/12 = 7.71875, 104.625/12 = 8.71875.
PRECUT_LENGTHS_FT = [Decimal('7.71875'), Decimal('8.71875')]
DIMENSIONS = ['2x4', '2x6']


def seed_precut_lengths(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    MaterialLength = apps.get_model('catalog', 'MaterialLength')

    products = MaterialProduct.objects.filter(
        account__isnull=True, species='SPF', grade='#2', nominal_dimension__in=DIMENSIONS,
    )
    for product in products:
        for length_ft in PRECUT_LENGTHS_FT:
            MaterialLength.objects.get_or_create(product=product, length_ft=length_ft)


def unseed_precut_lengths(apps, schema_editor):
    MaterialLength = apps.get_model('catalog', 'MaterialLength')
    MaterialLength.objects.filter(
        product__account__isnull=True, product__species='SPF', product__grade='#2',
        product__nominal_dimension__in=DIMENSIONS, length_ft__in=PRECUT_LENGTHS_FT,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_alter_materiallength_length_ft'),
    ]

    operations = [
        migrations.RunPython(seed_precut_lengths, unseed_precut_lengths),
    ]
