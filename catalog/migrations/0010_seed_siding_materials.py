from django.db import migrations
from django.utils.text import slugify

# Siding field materials, priced by the "square" (100 sqft of wall covered).
# Each is an `each` unit; the covering assembly's rule carries coverage_sqft=100,
# exactly like sheet goods (OSB is `each`, the rule supplies the 32 sqft coverage).
# name, category, species/material, grade/note, dimension
NEW_PRODUCTS = [
    ('Vinyl Siding (Square)', 'siding', 'Vinyl', 'D4', 'per square'),
    ('Clapboard Siding (Square)', 'siding', 'Cedar', 'clapboard', 'per square'),
    ('Fiber Cement Lap Siding (Square)', 'siding', 'Fiber Cement', 'lap', 'per square'),
    ('Cedar Shingle Siding (Square)', 'siding', 'Cedar', 'shingle', 'per square'),
    ('Board & Batten Siding (Square)', 'siding', 'Pine', 'board & batten', 'per square'),
]


def seed(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    for name, category, species, grade, dimension in NEW_PRODUCTS:
        if MaterialProduct.objects.filter(name=name, account__isnull=True).exists():
            continue
        MaterialProduct.objects.create(
            name=name, slug=slugify(name), category=category, species=species,
            grade=grade, nominal_dimension=dimension, input_type='each',
        )


def unseed(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    names = [row[0] for row in NEW_PRODUCTS]
    MaterialProduct.objects.filter(name__in=names, account__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0009_alter_materialproduct_category'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
