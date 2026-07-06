from decimal import Decimal

from django.db import migrations

# Per assembly: (name, tool_type, description, [rules])
# Rule: (material_name, role, formula_kind, {params})
ASSEMBLIES = [
    (
        '2x4 Wall - 16 in OC', 'line',
        'Interior 2x4 stud wall, 16" OC, single bottom plate, double top plate.',
        [
            ('2x4 SPF #2', 'Stud', 'per_spacing', {'extra': 1, 'waste_factor': Decimal('0.10')}),
            ('2x4 SPF #2', 'Top Plate', 'per_stock_length', {'multiplier': 2, 'waste_factor': Decimal('0.05')}),
            ('2x4 SPF #2', 'Bottom Plate', 'per_stock_length', {'multiplier': 1, 'waste_factor': Decimal('0.05')}),
        ],
    ),
    (
        '2x6 Exterior Wall on Slab - 16 in OC', 'line',
        'Exterior 2x6 wall with a pressure-treated bottom plate for concrete contact.',
        [
            ('2x6 SPF #2', 'Stud', 'per_spacing', {'extra': 1, 'waste_factor': Decimal('0.10')}),
            ('2x6 SPF #2', 'Top Plate', 'per_stock_length', {'multiplier': 2, 'waste_factor': Decimal('0.05')}),
            ('2x6 PT', 'Bottom Plate (PT)', 'per_stock_length', {'multiplier': 1, 'waste_factor': Decimal('0.05')}),
        ],
    ),
    (
        'LVL Beam 1-3/4x11-7/8 (Double)', 'line',
        'Two-ply LVL beam cut to the traced span.',
        [
            ('LVL 1-3/4x11-7/8', 'Beam Ply', 'per_length', {'multiplier': 2, 'waste_factor': Decimal('0')}),
        ],
    ),
    (
        '2x10 Floor Joists - 16 in OC', 'area',
        'Floor deck: 2x10 joists at 16" OC across the traced area, 2x10 rim around the perimeter, 3/4" T&G subfloor.',
        [
            ('2x10 SPF #2', 'Floor Joist', 'per_area_spacing', {'waste_factor': Decimal('0.05')}),
            ('2x10 SPF #2', 'Rim Board', 'per_stock_length', {'multiplier': 1, 'waste_factor': Decimal('0.05')}),
            ('Plywood 3/4 T&G 4x8 Subfloor', 'Subfloor', 'per_area_coverage', {'coverage_sqft': Decimal('32'), 'waste_factor': Decimal('0.10')}),
        ],
    ),
    (
        '2x8 Roof Rafters - 16 in OC', 'area',
        'Stick-framed roof plane: 2x8 rafters at 16" OC, 1/2" CDX sheathing, #30 felt.',
        [
            ('2x8 SPF #2', 'Rafter', 'per_area_spacing', {'waste_factor': Decimal('0.10')}),
            ('CDX 1/2 4x8 Roof Sheathing', 'Roof Sheathing', 'per_area_coverage', {'coverage_sqft': Decimal('32'), 'waste_factor': Decimal('0.10')}),
            ('Roofing Felt #30 Roll', 'Felt', 'per_area_coverage', {'coverage_sqft': Decimal('200'), 'waste_factor': Decimal('0.10')}),
        ],
    ),
    (
        'Roof Trusses - 24 in OC', 'area',
        'Trussed roof: custom-order trusses at 24" OC across the traced footprint, 1/2" CDX sheathing, #30 felt. Trace the building footprint and set spacing to 24.',
        [
            ('Roof Truss (custom order)', 'Truss', 'per_area_spacing', {'waste_factor': Decimal('0')}),
            ('CDX 1/2 4x8 Roof Sheathing', 'Roof Sheathing', 'per_area_coverage', {'coverage_sqft': Decimal('32'), 'waste_factor': Decimal('0.15')}),
            ('Roofing Felt #30 Roll', 'Felt', 'per_area_coverage', {'coverage_sqft': Decimal('200'), 'waste_factor': Decimal('0.10')}),
        ],
    ),
    (
        'Wall Sheathing - 7/16 OSB + House Wrap', 'area',
        'Exterior wall skin traced as an elevation area: 7/16" OSB plus house wrap.',
        [
            ('OSB 7/16 4x8 Wall Sheathing', 'Wall Sheathing', 'per_area_coverage', {'coverage_sqft': Decimal('32'), 'waste_factor': Decimal('0.10')}),
            ('House Wrap 9x100 Roll', 'House Wrap', 'per_area_coverage', {'coverage_sqft': Decimal('900'), 'waste_factor': Decimal('0')}),
        ],
    ),
    (
        'Window/Door Opening - 2x10 Header (2x6 Wall)', 'opening',
        'Framed opening in a 2x6 wall: double 2x10 header sized to the opening width plus bearing, king studs, trimmers, and cripples.',
        [
            ('2x10 SPF #2', 'Header', 'header', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'King Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Trimmer Stud', 'fixed_count', {'multiplier': 2, 'waste_factor': Decimal('0')}),
            ('2x6 SPF #2', 'Cripple Stud', 'per_spacing', {'extra': 0, 'waste_factor': Decimal('0.10')}),
        ],
    ),
    (
        '4x4 PT Post', 'count',
        'One pressure-treated 4x4 post per counted point.',
        [
            ('4x4 PT Post', 'Post', 'per_count', {'multiplier': 1, 'waste_factor': Decimal('0')}),
        ],
    ),
    (
        'Joist Hangers 2x10', 'count',
        'One 2x10 joist hanger per counted point.',
        [
            ('Joist Hanger 2x10', 'Joist Hanger', 'per_count', {'multiplier': 1, 'waste_factor': Decimal('0')}),
        ],
    ),
]


def seed(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    CalculationRule = apps.get_model('estimating', 'CalculationRule')
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')

    for name, tool_type, description, rules in ASSEMBLIES:
        assembly = Assembly.objects.create(name=name, tool_type=tool_type, description=description)
        for order, (material_name, role, formula_kind, params) in enumerate(rules, start=1):
            material = MaterialProduct.objects.get(name=material_name, account__isnull=True)
            CalculationRule.objects.create(
                assembly=assembly, material=material, role=role,
                formula_kind=formula_kind, order=order, **params,
            )


def unseed(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    names = [assembly[0] for assembly in ASSEMBLIES]
    Assembly.objects.filter(name__in=names, account__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0003_calculationrule_coverage_sqft_and_more'),
        ('catalog', '0004_seed_house_framing_materials'),
        ('plans', '0003_alter_toolpreset_tool_type_alter_trace_tool_type'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
