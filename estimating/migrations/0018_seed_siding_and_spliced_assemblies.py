from decimal import Decimal

from django.db import migrations

# Per assembly: (name, tool_type, category, description, [rules])
# Rule: (material_name, role, formula_kind, {params})
W10 = {'waste_factor': Decimal('0.10')}
W15 = {'waste_factor': Decimal('0.15')}
W00 = {'waste_factor': Decimal('0')}

# One "square" of siding covers 100 sqft of wall. Coverage lives on the rule
# (like sheet goods), so the same field material works at any exposure once you
# tune coverage_sqft. Waste covers overlap, corners, and cut-off.
ASSEMBLIES = [
    (
        'Vinyl Siding', 'area', 'siding_exterior',
        'Vinyl siding field over the exterior wall area, traced as an elevation. Priced by the square.',
        [
            ('Vinyl Siding (Square)', 'Vinyl Siding', 'per_area_coverage', {'coverage_sqft': Decimal('100'), **W10}),
        ],
    ),
    (
        'Clapboard Siding', 'area', 'siding_exterior',
        'Cedar clapboard field over the exterior wall area. Priced by the square.',
        [
            ('Clapboard Siding (Square)', 'Clapboard Siding', 'per_area_coverage', {'coverage_sqft': Decimal('100'), **W15}),
        ],
    ),
    (
        'Fiber Cement Lap Siding', 'area', 'siding_exterior',
        'Fiber cement lap siding field over the exterior wall area. Priced by the square.',
        [
            ('Fiber Cement Lap Siding (Square)', 'Fiber Cement Siding', 'per_area_coverage', {'coverage_sqft': Decimal('100'), **W10}),
        ],
    ),
    (
        'Cedar Shingle Siding', 'area', 'siding_exterior',
        'Cedar shingle siding field over the exterior wall area. Priced by the square.',
        [
            ('Cedar Shingle Siding (Square)', 'Shingle Siding', 'per_area_coverage', {'coverage_sqft': Decimal('100'), **W15}),
        ],
    ),
    (
        'Vinyl Siding + House Wrap', 'area', 'siding_exterior',
        'Complete wall skin: house wrap plus a vinyl siding field, traced as one elevation area.',
        [
            ('House Wrap 9x100 Roll', 'House Wrap', 'per_area_coverage', {'coverage_sqft': Decimal('900'), **W00}),
            ('Vinyl Siding (Square)', 'Vinyl Siding', 'per_area_coverage', {'coverage_sqft': Decimal('100'), **W10}),
        ],
    ),
    # Spliced built-up beam: demonstrates per_length_spliced. A long girder is
    # built from full-length stock spliced over posts, so a span longer than the
    # material's longest stock piece no longer errors - it orders enough pieces.
    (
        'Built-Up Beam - Triple 2x12 (Spliced)', 'line', 'floor_system',
        'Three-ply 2x12 built-up girder cut to the traced span, spliced over supports when the '
        'span is longer than the longest 2x12 stock piece. Add splice laps via the waste factor.',
        [
            ('2x12 SPF #2', 'Beam Ply', 'per_length_spliced', {'multiplier': 3, **W10}),
        ],
    ),
]


def seed(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    CalculationRule = apps.get_model('estimating', 'CalculationRule')
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')

    for name, tool_type, category, description, rules in ASSEMBLIES:
        if Assembly.objects.filter(name=name, tool_type=tool_type, account__isnull=True).exists():
            continue
        assembly = Assembly.objects.create(
            name=name, tool_type=tool_type, category=category, description=description,
        )
        for order, (material_name, role, formula_kind, params) in enumerate(rules, start=1):
            material = MaterialProduct.objects.get(name=material_name, account__isnull=True)
            CalculationRule.objects.create(
                assembly=assembly, material=material, role=role,
                formula_kind=formula_kind, order=order, **params,
            )


def unseed(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    names = [row[0] for row in ASSEMBLIES]
    Assembly.objects.filter(name__in=names, account__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0017_alter_calculationrule_formula_kind'),
        ('catalog', '0010_seed_siding_materials'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
