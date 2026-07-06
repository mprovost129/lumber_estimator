from decimal import Decimal

from django.db import migrations

# Only the one existing wall assembly whose name/description is unambiguous
# gets tagged - '2x4 Wall - 16 in OC' and '2x6 Wall - 16 in OC' are both
# explicitly described as usable for either bearing or non-bearing walls, and
# 'LVL Beam 1-3/4x11-7/8 (Double)' has no flush/dropped signal at all -
# guessing on any of these would risk silently mis-tagging an existing
# account's real walls/beams into the wrong toolbar variant. They're left
# unclassified (still selectable manually) with a clarifying description
# instead; new, clearly-scoped assemblies are added below for the toolbar
# variants that need real data to resolve against.
EXTERIOR_WALL_ASSEMBLY_NAME = '2x6 Exterior Wall on Slab - 16 in OC'

LEGACY_DESCRIPTION_SUFFIX = ' (Legacy: not tagged to a specific wall/opening subtype - pick manually.)'
LEGACY_ASSEMBLY_NAMES = [
    '2x4 Wall - 16 in OC',
    '2x6 Wall - 16 in OC',
    'LVL Beam 1-3/4x11-7/8 (Double)',
    'Window/Door Opening - 2x10 Header (2x6 Wall)',
]

# Per assembly: (name, tool_type, category, extra_fields, description, [rules])
# Rule: (material_name, role, formula_kind, {params})
NEW_ASSEMBLIES = [
    (
        '2x6 Interior Bearing Wall - 16 in OC', 'line', 'wall_system', {'wall_subtype': 'interior_bearing'},
        'Interior 2x6 bearing wall, 16" OC, single bottom plate, double top plate.',
        [
            ('2x6 SPF #2', 'Stud', 'per_spacing', {'extra': 1, 'waste_factor': Decimal('0.10')}),
            ('2x6 SPF #2', 'Top Plate', 'per_stock_length', {'multiplier': 2, 'waste_factor': Decimal('0.05')}),
            ('2x6 SPF #2', 'Bottom Plate', 'per_stock_length', {'multiplier': 1, 'waste_factor': Decimal('0.05')}),
        ],
    ),
    (
        '2x4 Interior Non-Bearing Wall - 16 in OC', 'line', 'wall_system', {'wall_subtype': 'interior_non_bearing'},
        'Interior 2x4 non-bearing partition, 16" OC, single bottom plate, double top plate.',
        [
            ('2x4 SPF #2', 'Stud', 'per_spacing', {'extra': 1, 'waste_factor': Decimal('0.10')}),
            ('2x4 SPF #2', 'Top Plate', 'per_stock_length', {'multiplier': 2, 'waste_factor': Decimal('0.05')}),
            ('2x4 SPF #2', 'Bottom Plate', 'per_stock_length', {'multiplier': 1, 'waste_factor': Decimal('0.05')}),
        ],
    ),
    (
        'LVL Beam - Flush (Double 1-3/4x11-7/8)', 'line', 'wall_system', {'beam_type': 'flush'},
        'Two-ply LVL beam cut to the traced span, set flush within the floor/ceiling depth.',
        [
            ('LVL 1-3/4x11-7/8', 'Beam Ply', 'per_length', {'multiplier': 2, 'waste_factor': Decimal('0')}),
        ],
    ),
    (
        'LVL Beam - Dropped (Double 1-3/4x11-7/8)', 'line', 'wall_system', {'beam_type': 'dropped'},
        'Two-ply LVL beam cut to the traced span, dropped below the framing.',
        [
            ('LVL 1-3/4x11-7/8', 'Beam Ply', 'per_length', {'multiplier': 2, 'waste_factor': Decimal('0')}),
        ],
    ),
    (
        'Window Opening - Exterior Wall Header', 'opening', 'openings',
        {'opening_kind': 'window', 'wall_subtype': 'exterior'},
        'Window in an exterior 2x6 wall: double 2x10 header, king studs, trimmers, and cripples.',
        [
            ('2x10 SPF #2', 'Header', 'header', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'King Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Trimmer Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Cripple Stud', 'per_spacing', {'extra': 0, 'waste_factor': Decimal('0.10')}),
        ],
    ),
    (
        'Door Opening - Exterior Wall Header', 'opening', 'openings',
        {'opening_kind': 'door', 'wall_subtype': 'exterior'},
        'Door in an exterior 2x6 wall: double 2x10 header, king studs, trimmers, and cripples.',
        [
            ('2x10 SPF #2', 'Header', 'header', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'King Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Trimmer Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Cripple Stud', 'per_spacing', {'extra': 0, 'waste_factor': Decimal('0.10')}),
        ],
    ),
    (
        'Window Opening - Interior Bearing Wall Header', 'opening', 'openings',
        {'opening_kind': 'window', 'wall_subtype': 'interior_bearing'},
        'Window in an interior 2x6 bearing wall: double 2x10 header, king studs, trimmers, and cripples.',
        [
            ('2x10 SPF #2', 'Header', 'header', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'King Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Trimmer Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Cripple Stud', 'per_spacing', {'extra': 0, 'waste_factor': Decimal('0.10')}),
        ],
    ),
    (
        'Door Opening - Interior Bearing Wall Header', 'opening', 'openings',
        {'opening_kind': 'door', 'wall_subtype': 'interior_bearing'},
        'Door in an interior 2x6 bearing wall: double 2x10 header, king studs, trimmers, and cripples.',
        [
            ('2x10 SPF #2', 'Header', 'header', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'King Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Trimmer Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Cripple Stud', 'per_spacing', {'extra': 0, 'waste_factor': Decimal('0.10')}),
        ],
    ),
    (
        'Window Opening - Interior Non-Bearing Wall (Light)', 'opening', 'openings',
        {'opening_kind': 'window', 'wall_subtype': 'interior_non_bearing'},
        (
            'Window in a non-bearing 2x4 partition: no structural header needed, just king/trimmer studs '
            'and a single-ply flat header for drywall backing.'
        ),
        [
            ('2x4 SPF #2', 'King Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x4 SPF #2', 'Trimmer Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x4 SPF #2', 'Header', 'header', {'multiplier': 1, 'waste_factor': Decimal('0')}),
        ],
    ),
    (
        'Door Opening - Interior Non-Bearing Wall (Light)', 'opening', 'openings',
        {'opening_kind': 'door', 'wall_subtype': 'interior_non_bearing'},
        (
            'Door in a non-bearing 2x4 partition: no structural header needed, just king/trimmer studs '
            'and a single-ply flat header for drywall backing.'
        ),
        [
            ('2x4 SPF #2', 'King Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x4 SPF #2', 'Trimmer Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x4 SPF #2', 'Header', 'header', {'multiplier': 1, 'waste_factor': Decimal('0')}),
        ],
    ),
]


def seed(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    CalculationRule = apps.get_model('estimating', 'CalculationRule')
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')

    Assembly.objects.filter(name=EXTERIOR_WALL_ASSEMBLY_NAME, account__isnull=True).update(
        wall_subtype='exterior',
    )

    for name in LEGACY_ASSEMBLY_NAMES:
        assembly = Assembly.objects.filter(name=name, account__isnull=True).first()
        if assembly is not None and not assembly.description.endswith(LEGACY_DESCRIPTION_SUFFIX):
            assembly.description += LEGACY_DESCRIPTION_SUFFIX
            assembly.save(update_fields=['description'])

    for name, tool_type, category, extra_fields, description, rules in NEW_ASSEMBLIES:
        assembly = Assembly.objects.create(
            name=name, tool_type=tool_type, category=category, description=description, **extra_fields,
        )
        for order, (material_name, role, formula_kind, params) in enumerate(rules, start=1):
            material = MaterialProduct.objects.get(name=material_name, account__isnull=True)
            CalculationRule.objects.create(
                assembly=assembly, material=material, role=role,
                formula_kind=formula_kind, order=order, **params,
            )


def unseed(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')

    Assembly.objects.filter(name=EXTERIOR_WALL_ASSEMBLY_NAME, account__isnull=True).update(wall_subtype=None)

    for name in LEGACY_ASSEMBLY_NAMES:
        assembly = Assembly.objects.filter(name=name, account__isnull=True).first()
        if assembly is not None and assembly.description.endswith(LEGACY_DESCRIPTION_SUFFIX):
            assembly.description = assembly.description[:-len(LEGACY_DESCRIPTION_SUFFIX)]
            assembly.save(update_fields=['description'])

    new_names = [assembly[0] for assembly in NEW_ASSEMBLIES]
    Assembly.objects.filter(name__in=new_names, account__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0014_add_wall_subtype_opening_kind_beam_type'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
