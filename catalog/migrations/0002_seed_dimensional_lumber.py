from django.db import migrations

DIMENSIONS = ['2x4', '2x6', '2x8', '2x10', '2x12']
STOCK_LENGTHS_FT = range(8, 25, 2)  # 8' to 24' in 2' increments
DEFAULT_LENGTH_FT = 16


def seed_products(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    MaterialLength = apps.get_model('catalog', 'MaterialLength')

    for dimension in DIMENSIONS:
        product = MaterialProduct.objects.create(
            species='SPF',
            grade='#2',
            nominal_dimension=dimension,
            name=f'{dimension} SPF #2',
            sale_unit='each',
        )
        for length_ft in STOCK_LENGTHS_FT:
            MaterialLength.objects.create(
                product=product,
                length_ft=length_ft,
                is_default=(length_ft == DEFAULT_LENGTH_FT),
            )


def unseed_products(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    MaterialProduct.objects.filter(species='SPF', grade='#2', nominal_dimension__in=DIMENSIONS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_products, unseed_products),
    ]
