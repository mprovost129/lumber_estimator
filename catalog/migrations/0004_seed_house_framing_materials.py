from django.db import migrations

# (name, species, grade, nominal_dimension, input_type, quantity_per_box, lengths, default_length)
MATERIALS = [
    # Pressure-treated plates and posts
    ('2x4 PT', 'SYP', 'PT', '2x4', 'ft', None, [8, 10, 12, 16], 16),
    ('2x6 PT', 'SYP', 'PT', '2x6', 'ft', None, [8, 10, 12, 16], 16),
    ('4x4 PT Post', 'SYP', 'PT', '4x4', 'ft', None, [8, 10, 12], 8),
    ('6x6 PT Post', 'SYP', 'PT', '6x6', 'ft', None, [8, 10, 12], 8),
    # Engineered beams
    ('LVL 1-3/4x9-1/2', 'LVL', '2.0E', '1.75x9.5', 'ft', None, [8, 10, 12, 14, 16, 18, 20, 24], 16),
    ('LVL 1-3/4x11-7/8', 'LVL', '2.0E', '1.75x11.875', 'ft', None, [8, 10, 12, 14, 16, 18, 20, 24], 16),
    # Sheet goods (each; assembly rules carry the 32 sqft coverage)
    ('OSB 7/16 4x8 Wall Sheathing', 'OSB', '', '7/16x4x8', 'each', None, [], None),
    ('CDX 1/2 4x8 Roof Sheathing', 'CDX', '', '1/2x4x8', 'each', None, [], None),
    ('Plywood 3/4 T&G 4x8 Subfloor', 'Plywood', 'T&G', '3/4x4x8', 'each', None, [], None),
    # Rolls (each; coverage on the rule)
    ('House Wrap 9x100 Roll', '', '', "9'x100'", 'each', None, [], None),
    ('Roofing Felt #30 Roll', '', '#30', '', 'each', None, [], None),
    # Per-unit hardware and custom-order items
    ('Roof Truss (custom order)', '', '', '', 'each', None, [], None),
    ('Joist Hanger 2x10', '', '', '2x10', 'each', None, [], None),
    ('Sill Seal 5-1/2x50 Roll', '', '', '5.5"x50\'', 'each', None, [], None),
    # Fasteners
    ('Framing Nails 3-1/4 (Box)', '', '', '3-1/4"', 'box', 2500, [], None),
    ('Sheathing Nails 2-3/8 (Box)', '', '', '2-3/8"', 'box', 2500, [], None),
]


def seed(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    MaterialLength = apps.get_model('catalog', 'MaterialLength')
    from django.utils.text import slugify

    for name, species, grade, dimension, input_type, per_box, lengths, default in MATERIALS:
        product = MaterialProduct.objects.create(
            name=name, slug=slugify(name), species=species, grade=grade,
            nominal_dimension=dimension, input_type=input_type,
            quantity_per_box=per_box,
        )
        for length_ft in lengths:
            MaterialLength.objects.create(
                product=product, length_ft=length_ft, is_default=(length_ft == default),
            )


def unseed(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    names = [material[0] for material in MATERIALS]
    MaterialProduct.objects.filter(name__in=names, account__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_material_input_types'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
