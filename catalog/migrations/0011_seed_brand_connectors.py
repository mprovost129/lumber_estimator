from django.db import migrations
from django.utils.text import slugify

# Common, widely stocked connector SKUs from the two big manufacturers:
# Simpson Strong-Tie and USP (MiTek). Intentionally limited to the everyday
# residential lineup a lumberyard actually carries; oddball or engineered-only
# SKUs belong in an account's own import, not the global catalog.
# (name, species [used as brand], grade [series note], dimension [fits])
SIMPSON = [
    # Face-mount joist hangers (LUS standard, HUS heavy)
    ('Simpson LUS24 Joist Hanger', 'Simpson Strong-Tie', 'LUS', '2x4'),
    ('Simpson LUS26 Joist Hanger', 'Simpson Strong-Tie', 'LUS', '2x6'),
    ('Simpson LUS28 Joist Hanger', 'Simpson Strong-Tie', 'LUS', '2x8'),
    ('Simpson LUS210 Joist Hanger', 'Simpson Strong-Tie', 'LUS', '2x10'),
    ('Simpson LUS212 Joist Hanger', 'Simpson Strong-Tie', 'LUS', '2x12'),
    ('Simpson HUS26 Heavy Joist Hanger', 'Simpson Strong-Tie', 'HUS', '2x6'),
    ('Simpson HUS28 Heavy Joist Hanger', 'Simpson Strong-Tie', 'HUS', '2x8'),
    ('Simpson HUS210 Heavy Joist Hanger', 'Simpson Strong-Tie', 'HUS', '2x10'),
    ('Simpson HUS412 Heavy Joist Hanger', 'Simpson Strong-Tie', 'HUS', '4x12'),
    # Double / girder hangers
    ('Simpson LUS26-2 Double Joist Hanger', 'Simpson Strong-Tie', 'LUS', '(2) 2x6'),
    ('Simpson LUS28-2 Double Joist Hanger', 'Simpson Strong-Tie', 'LUS', '(2) 2x8'),
    ('Simpson LUS210-2 Double Joist Hanger', 'Simpson Strong-Tie', 'LUS', '(2) 2x10'),
    ('Simpson HGUS410 Girder Hanger', 'Simpson Strong-Tie', 'HGUS', '(2-3) 2x10 / 4x10'),
    # Concealed / skewed
    ('Simpson LSSR210 Skewable Rafter Hanger', 'Simpson Strong-Tie', 'LSSR', '2x10'),
    ('Simpson HUC210 Concealed Flange Hanger', 'Simpson Strong-Tie', 'HUC', '2x10'),
    # I-joist and engineered
    ('Simpson IUS2.06/9.5 I-Joist Hanger', 'Simpson Strong-Tie', 'IUS', "9-1/2 I-joist"),
    ('Simpson IUS2.06/11.88 I-Joist Hanger', 'Simpson Strong-Tie', 'IUS', "11-7/8 I-joist"),
    ('Simpson HU9 Beam Hanger', 'Simpson Strong-Tie', 'HU', 'LVL / built-up'),
    # Hurricane ties, angles, straps
    ('Simpson H1 Hurricane Tie', 'Simpson Strong-Tie', 'H', 'rafter to plate'),
    ('Simpson H2.5A Hurricane Tie', 'Simpson Strong-Tie', 'H', 'rafter to plate'),
    ('Simpson H10A Hurricane Tie', 'Simpson Strong-Tie', 'H', 'rafter to plate'),
    ('Simpson A35 Framing Angle', 'Simpson Strong-Tie', 'A', 'multi-purpose'),
    ('Simpson LSTA24 Strap Tie', 'Simpson Strong-Tie', 'LSTA', "24 in strap"),
    ('Simpson MST48 Strap Tie', 'Simpson Strong-Tie', 'MST', "48 in strap"),
    ('Simpson CS16 Coiled Strap (Roll)', 'Simpson Strong-Tie', 'CS', "16 ga coil"),
    # Post bases and caps
    ('Simpson ABU44Z Post Base', 'Simpson Strong-Tie', 'ABU', '4x4'),
    ('Simpson ABU66Z Post Base', 'Simpson Strong-Tie', 'ABU', '6x6'),
    ('Simpson BC4 Post Cap/Base', 'Simpson Strong-Tie', 'BC', '4x'),
    ('Simpson BCS2-2/4 Post Cap', 'Simpson Strong-Tie', 'BCS', '(2) 2x to 4x post'),
    ('Simpson AC4 Post Cap', 'Simpson Strong-Tie', 'AC', '4x'),
    # Deck hardware
    ('Simpson DTT1Z Deck Tension Tie', 'Simpson Strong-Tie', 'DTT', 'guard post'),
    ('Simpson DTT2Z Deck Tension Tie', 'Simpson Strong-Tie', 'DTT', 'ledger / guard post'),
    # Hold-downs
    ('Simpson HDU2 Hold-Down', 'Simpson Strong-Tie', 'HDU', 'shear wall'),
    ('Simpson HDU5 Hold-Down', 'Simpson Strong-Tie', 'HDU', 'shear wall'),
]

USP = [
    # Face-mount joist hangers (JUS standard, THD heavy)
    ('USP JUS24 Joist Hanger', 'USP (MiTek)', 'JUS', '2x4'),
    ('USP JUS26 Joist Hanger', 'USP (MiTek)', 'JUS', '2x6'),
    ('USP JUS28 Joist Hanger', 'USP (MiTek)', 'JUS', '2x8'),
    ('USP JUS210 Joist Hanger', 'USP (MiTek)', 'JUS', '2x10'),
    ('USP JUS212 Joist Hanger', 'USP (MiTek)', 'JUS', '2x12'),
    ('USP THD26 Heavy Joist Hanger', 'USP (MiTek)', 'THD', '2x6'),
    ('USP THD28 Heavy Joist Hanger', 'USP (MiTek)', 'THD', '2x8'),
    ('USP THD210 Heavy Joist Hanger', 'USP (MiTek)', 'THD', '2x10'),
    # Doubles
    ('USP JUS26-2 Double Joist Hanger', 'USP (MiTek)', 'JUS', '(2) 2x6'),
    ('USP JUS210-2 Double Joist Hanger', 'USP (MiTek)', 'JUS', '(2) 2x10'),
    # Hurricane ties, angles, straps
    ('USP RT7 Rafter Tie', 'USP (MiTek)', 'RT', 'rafter to plate'),
    ('USP RT15 Rafter Tie', 'USP (MiTek)', 'RT', 'rafter to plate'),
    ('USP MP34 Framing Angle', 'USP (MiTek)', 'MP', 'multi-purpose'),
    ('USP LSTA24 Strap Tie', 'USP (MiTek)', 'LSTA', "24 in strap"),
    # Post bases and caps
    ('USP PA44 Post Base', 'USP (MiTek)', 'PA', '4x4'),
    ('USP PA66 Post Base', 'USP (MiTek)', 'PA', '6x6'),
    ('USP PC44 Post Cap', 'USP (MiTek)', 'PC', '4x4'),
    ('USP PC66 Post Cap', 'USP (MiTek)', 'PC', '6x6'),
    # Deck
    ('USP DTB-TZ Deck Tie Back', 'USP (MiTek)', 'DTB', 'ledger / guard post'),
]


def seed(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    for name, brand, series, fits in SIMPSON + USP:
        if MaterialProduct.objects.filter(name=name, account__isnull=True).exists():
            continue
        MaterialProduct.objects.create(
            name=name, slug=slugify(name), category='connectors',
            species=brand, grade=series, nominal_dimension=fits, input_type='each',
        )


def unseed(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    names = [row[0] for row in SIMPSON + USP]
    MaterialProduct.objects.filter(name__in=names, account__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0010_seed_siding_materials'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
