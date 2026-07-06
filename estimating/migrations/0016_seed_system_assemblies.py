from decimal import Decimal

from django.db import migrations

# Per assembly: (name, tool_type, category, description, [rules])
# Rule: (material_name, role, formula_kind, {params})
#
# tool_type drives which geometry/measurement feeds the rules:
#   line  -> length_ft   (per_stock_length runs, per_length beams)
#   area  -> area/bbox   (per_area_spacing members, per_area_coverage sheets/rolls)
#   count -> count       (per_count)
# category groups the line on the material list (build order).

W05 = {'waste_factor': Decimal('0.05')}
W10 = {'waste_factor': Decimal('0.10')}
W15 = {'waste_factor': Decimal('0.15')}
W00 = {'waste_factor': Decimal('0')}

ASSEMBLIES = [
    # ---------------- Foundation & Sill ----------------
    (
        'Sill Plate - 2x6 PT', 'line', 'foundation_sill',
        'Pressure-treated 2x6 sill plate run over the foundation perimeter, cut from stock.',
        [
            ('2x6 PT', 'Sill Plate (PT)', 'per_stock_length', {'multiplier': 1, **W05}),
        ],
    ),
    (
        'Anchor Bolts', 'count', 'foundation_sill',
        'One 1/2x10 anchor bolt per counted point. Count one per plate end and roughly every 6 ft.',
        [
            ('Anchor Bolt 1/2x10', 'Anchor Bolt', 'per_count', {'multiplier': 1, **W00}),
        ],
    ),

    # ---------------- Floor System (additions) ----------------
    (
        'Floor Beam - Dropped (Double 1-3/4x11-7/8 LVL)', 'line', 'floor_system',
        'Two-ply LVL floor girder cut to the traced span.',
        [
            ('LVL 1-3/4x11-7/8', 'Floor Beam Ply', 'per_length', {'multiplier': 2, **W00}),
        ],
    ),
    (
        'Subfloor - 3/4 T&G + Adhesive', 'area', 'floor_system',
        '3/4" tongue-and-groove subfloor sheets over the floor area, plus subfloor adhesive.',
        [
            ('Plywood 3/4 T&G 4x8 Subfloor', 'Subfloor', 'per_area_coverage', {'coverage_sqft': Decimal('32'), **W10}),
            ('Subfloor Adhesive 28oz', 'Subfloor Adhesive', 'per_area_coverage', {'coverage_sqft': Decimal('80'), **W00}),
        ],
    ),

    # ---------------- Stairs ----------------
    (
        'Stair Stringers (per flight)', 'count', 'stairs',
        'Three 2x12 stringers per counted flight. Add a fourth for stairs wider than 36 in.',
        [
            ('2x12 SPF #2', 'Stair Stringer', 'per_count', {'multiplier': 3, **W00}),
        ],
    ),
    (
        'Stair Landing Framing', 'area', 'stairs',
        'A landing framed like a small floor: 2x8 joists at spacing plus 3/4" subfloor.',
        [
            ('2x8 SPF #2', 'Landing Joist', 'per_area_spacing', W05),
            ('Plywood 3/4 T&G 4x8 Subfloor', 'Landing Sheathing', 'per_area_coverage', {'coverage_sqft': Decimal('32'), **W10}),
        ],
    ),

    # ---------------- Ceiling ----------------
    (
        'Ceiling Joists - 16 in OC', 'area', 'ceiling',
        '2x8 ceiling joists across the traced area at spacing, with a 2x8 ceiling rim around the perimeter.',
        [
            ('2x8 SPF #2', 'Ceiling Joist', 'per_area_spacing', W05),
            ('2x8 SPF #2', 'Ceiling Rim', 'per_stock_length', {'multiplier': 1, **W05}),
        ],
    ),
    (
        'Ceiling Strapping - 16 in OC', 'area', 'ceiling',
        '1x3 strapping run across the ceiling joists at spacing.',
        [
            ('1x3 Pine', 'Strapping', 'per_area_spacing', W10),
        ],
    ),
    (
        'Ceiling Beam - Dropped (Double 1-3/4x9-1/2 LVL)', 'line', 'ceiling',
        'Two-ply LVL ceiling beam cut to the traced span.',
        [
            ('LVL 1-3/4x9-1/2', 'Ceiling Beam Ply', 'per_length', {'multiplier': 2, **W00}),
        ],
    ),

    # ---------------- Roof (additions) ----------------
    (
        'Asphalt Shingle Roofing', 'area', 'roof',
        'Finished roofing over the sloped roof area: architectural shingle bundles plus #15 felt underlayment. Trace the true sloped area.',
        [
            ('Architectural Shingles (Bundle)', 'Shingles', 'per_area_coverage', {'coverage_sqft': Decimal('33.33'), **W15}),
            ('Roofing Felt #15 Roll', 'Underlayment', 'per_area_coverage', {'coverage_sqft': Decimal('400'), **W10}),
        ],
    ),
    (
        'Ridge Board - 2x10', 'line', 'roof',
        '2x10 ridge board run along the traced ridge line, cut from stock.',
        [
            ('2x10 SPF #2', 'Ridge Board', 'per_stock_length', {'multiplier': 1, **W05}),
        ],
    ),
    (
        'Roof Edge - Drip + Sub-Fascia', 'line', 'roof',
        'Eave/rake edge run: aluminum drip edge in 10 ft pieces plus a 2x8 sub-fascia.',
        [
            ('Drip Edge 10ft', 'Drip Edge', 'per_stock_length', {'multiplier': 1, **W10}),
            ('2x8 SPF #2', 'Sub-Fascia', 'per_stock_length', {'multiplier': 1, **W05}),
        ],
    ),
    (
        'Collar Ties - 2x6', 'count', 'roof',
        'One 2x6 collar tie per counted point. Count one for every other rafter pair, typical.',
        [
            ('2x6 SPF #2', 'Collar Tie', 'per_count', {'multiplier': 1, **W00}),
        ],
    ),
    (
        'Roof Hardware - Hurricane Ties', 'count', 'roof',
        'One hurricane tie per counted rafter or truss bearing point.',
        [
            ('Hurricane Tie H2.5A', 'Hurricane Tie', 'per_count', {'multiplier': 1, **W00}),
        ],
    ),

    # ---------------- Siding & Exterior Trim ----------------
    (
        'House Wrap', 'area', 'siding_exterior',
        'Weather-resistive barrier over the exterior wall area, traced as an elevation.',
        [
            ('House Wrap 9x100 Roll', 'House Wrap', 'per_area_coverage', {'coverage_sqft': Decimal('900'), **W00}),
        ],
    ),
    (
        'Fascia & Frieze Trim - 1x8 / 1x4', 'line', 'siding_exterior',
        'Eave/gable trim run: 1x8 fascia and a 1x4 frieze, cut from stock.',
        [
            ('1x8 Pine', 'Fascia', 'per_stock_length', {'multiplier': 1, **W10}),
            ('1x4 Pine', 'Frieze', 'per_stock_length', {'multiplier': 1, **W10}),
        ],
    ),
    (
        'Corner Trim - 1x4', 'line', 'siding_exterior',
        'Inside and outside corner boards, two 1x4 pieces per corner run.',
        [
            ('1x4 Pine', 'Corner Trim', 'per_stock_length', {'multiplier': 2, **W10}),
        ],
    ),

    # ---------------- Exterior Deck ----------------
    (
        'Deck Joists - 16 in OC (PT)', 'area', 'exterior_deck',
        'Pressure-treated 2x8 deck joists across the traced deck area, with a 2x8 PT rim.',
        [
            ('2x8 PT', 'Deck Joist (PT)', 'per_area_spacing', W05),
            ('2x8 PT', 'Deck Rim (PT)', 'per_stock_length', {'multiplier': 1, **W05}),
        ],
    ),
    (
        'Deck Beam - Dropped (Double 2x10 PT)', 'line', 'exterior_deck',
        'Two-ply pressure-treated 2x10 deck beam cut to the traced span.',
        [
            ('2x10 PT', 'Deck Beam Ply (PT)', 'per_length', {'multiplier': 2, **W00}),
        ],
    ),
    (
        'Deck Ledger - 2x10 PT', 'line', 'exterior_deck',
        'Pressure-treated 2x10 ledger fastened to the house, cut from stock.',
        [
            ('2x10 PT', 'Deck Ledger (PT)', 'per_stock_length', {'multiplier': 1, **W05}),
        ],
    ),
    (
        'Decking - 5/4x6 PT', 'area', 'exterior_deck',
        '5/4x6 pressure-treated deck boards over the deck area. Coverage assumes 16 ft boards.',
        [
            ('5/4x6 PT Decking', 'Decking (PT)', 'per_area_coverage', {'coverage_sqft': Decimal('7.33'), **W10}),
        ],
    ),
    (
        'Deck Posts - 6x6 PT', 'count', 'exterior_deck',
        'One 6x6 pressure-treated post per counted footing.',
        [
            ('6x6 PT Post', 'Deck Post (PT)', 'per_count', {'multiplier': 1, **W00}),
        ],
    ),
    (
        'Deck Footings - Sonotube 10in', 'count', 'exterior_deck',
        'One 10 in concrete form tube per counted footing.',
        [
            ('Sonotube 10in', 'Footing Form', 'per_count', {'multiplier': 1, **W00}),
        ],
    ),
    (
        'Deck Railing (per section)', 'count', 'exterior_deck',
        'One 6 ft railing kit per counted section.',
        [
            ('Deck Railing Kit 6ft', 'Railing Kit', 'per_count', {'multiplier': 1, **W00}),
        ],
    ),

    # ---------------- Miscellaneous ----------------
    (
        'Bulkhead', 'count', 'misc',
        'One bulkhead door per counted location.',
        [
            ('Bulkhead Door', 'Bulkhead', 'per_count', {'multiplier': 1, **W00}),
        ],
    ),
    (
        'Blocking - 2x6 (per run)', 'line', 'misc',
        'Fire blocking, backing, or nailers run along a line, cut from 2x6 stock.',
        [
            ('2x6 SPF #2', 'Blocking', 'per_stock_length', {'multiplier': 1, **W10}),
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
        ('estimating', '0015_seed_semantic_tool_assemblies'),
        ('catalog', '0008_seed_full_catalog'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
