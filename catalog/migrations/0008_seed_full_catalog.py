from django.db import migrations
from django.utils.text import slugify

# Reusable stock-length sets (feet) with the default piece length marked by DEFAULT.
DIM = [8, 10, 12, 14, 16, 18, 20]
DIM_LONG = [8, 10, 12, 14, 16, 18, 20, 24]
BOARD = [8, 10, 12, 16]
PT_DECK = [8, 10, 12, 16, 20]
LVL = [8, 10, 12, 14, 16, 18, 20, 24]
IJOIST = [16, 20, 24, 28, 32, 36, 40]
DRIP = [10]

# Category backfill for the products already seeded by earlier migrations.
EXISTING_CATEGORIES = {
    '2x4 SPF #2': 'dimensional', '2x6 SPF #2': 'dimensional', '2x8 SPF #2': 'dimensional',
    '2x10 SPF #2': 'dimensional', '2x12 SPF #2': 'dimensional',
    '2x4 PT': 'pressure_treated', '2x6 PT': 'pressure_treated',
    '4x4 PT Post': 'pressure_treated', '6x6 PT Post': 'pressure_treated',
    'LVL 1-3/4x9-1/2': 'engineered', 'LVL 1-3/4x11-7/8': 'engineered',
    'OSB 7/16 4x8 Wall Sheathing': 'sheathing', 'CDX 1/2 4x8 Roof Sheathing': 'sheathing',
    'Plywood 3/4 T&G 4x8 Subfloor': 'subfloor',
    'House Wrap 9x100 Roll': 'weather_barrier', 'Sill Seal 5-1/2x50 Roll': 'weather_barrier',
    'Roofing Felt #30 Roll': 'roofing',
    'Roof Truss (custom order)': 'engineered',
    'Joist Hanger 2x10': 'connectors',
    'Framing Nails 3-1/4 (Box)': 'fasteners', 'Sheathing Nails 2-3/8 (Box)': 'fasteners',
}

# New products.
# ft:   (name, category, species, grade, dimension, 'ft', lengths, default_length)
# box:  (name, category, species, grade, dimension, 'box', qty_per_box)
# each: (name, category, species, grade, dimension, 'each')
FT = 'ft'
BOX = 'box'
EACH = 'each'

NEW_PRODUCTS = [
    # --- Dimensional Lumber ---
    ('2x3 SPF #2', 'dimensional', 'SPF', '#2', '2x3', FT, [8, 10, 12], 8),

    # --- Pressure-Treated (fill out the range) ---
    ('2x8 PT', 'pressure_treated', 'SYP', 'PT', '2x8', FT, PT_DECK, 16),
    ('2x10 PT', 'pressure_treated', 'SYP', 'PT', '2x10', FT, PT_DECK, 16),
    ('2x12 PT', 'pressure_treated', 'SYP', 'PT', '2x12', FT, PT_DECK, 16),
    ('1x4 PT', 'pressure_treated', 'SYP', 'PT', '1x4', FT, BOARD, 12),
    ('1x6 PT', 'pressure_treated', 'SYP', 'PT', '1x6', FT, BOARD, 12),

    # --- Boards & Trim ---
    ('1x2 Pine', 'boards', 'Pine', '', '1x2', FT, BOARD, 12),
    ('1x3 Pine', 'boards', 'Pine', '', '1x3', FT, BOARD, 12),
    ('1x4 Pine', 'boards', 'Pine', '', '1x4', FT, BOARD, 12),
    ('1x6 Pine', 'boards', 'Pine', '', '1x6', FT, BOARD, 12),
    ('1x8 Pine', 'boards', 'Pine', '', '1x8', FT, BOARD, 12),
    ('1x10 Pine', 'boards', 'Pine', '', '1x10', FT, BOARD, 12),
    ('1x12 Pine', 'boards', 'Pine', '', '1x12', FT, BOARD, 12),
    ('5/4x6 Pine', 'boards', 'Pine', '', '5/4x6', FT, BOARD, 12),

    # --- Engineered Lumber ---
    ('LVL 1-3/4x7-1/4', 'engineered', 'LVL', '2.0E', '1.75x7.25', FT, LVL, 16),
    ('LVL 1-3/4x14', 'engineered', 'LVL', '2.0E', '1.75x14', FT, LVL, 16),
    ('LVL 1-3/4x16', 'engineered', 'LVL', '2.0E', '1.75x16', FT, LVL, 16),
    ('LSL 1-1/2x11-7/8 Rim', 'engineered', 'LSL', '1.55E', '1.5x11.875', FT, LVL, 16),
    ('PSL 3-1/2x11-1/4', 'engineered', 'PSL', '2.0E', '3.5x11.25', FT, LVL, 16),
    ('Glulam 3-1/2x9', 'engineered', 'Glulam', '24F', '3.5x9', FT, LVL, 16),
    ('I-Joist 9-1/2', 'engineered', 'I-Joist', '', '9.5', FT, IJOIST, 24),
    ('I-Joist 11-7/8', 'engineered', 'I-Joist', '', '11.875', FT, IJOIST, 24),
    ('I-Joist 14', 'engineered', 'I-Joist', '', '14', FT, IJOIST, 24),
    ('I-Joist 16', 'engineered', 'I-Joist', '', '16', FT, IJOIST, 24),
    ('Floor Truss (custom order)', 'engineered', '', '', '', EACH),

    # --- Sheathing & Panels ---
    ('OSB 1/2 4x8', 'sheathing', 'OSB', '', '1/2x4x8', EACH),
    ('OSB 5/8 4x8', 'sheathing', 'OSB', '', '5/8x4x8', EACH),
    ('OSB 3/4 4x8', 'sheathing', 'OSB', '', '3/4x4x8', EACH),
    ('CDX 5/8 4x8', 'sheathing', 'CDX', '', '5/8x4x8', EACH),
    ('CDX 3/4 4x8', 'sheathing', 'CDX', '', '3/4x4x8', EACH),
    ('Plywood 1/2 4x8', 'sheathing', 'Plywood', '', '1/2x4x8', EACH),
    ('Plywood 5/8 4x8', 'sheathing', 'Plywood', '', '5/8x4x8', EACH),
    ('ZIP System 7/16 4x8', 'sheathing', 'ZIP', '', '7/16x4x8', EACH),
    ('ZIP System 1/2 4x8', 'sheathing', 'ZIP', '', '1/2x4x8', EACH),
    ('Drywall 1/2 4x8', 'sheathing', 'Gypsum', '', '1/2x4x8', EACH),
    ('Drywall 5/8 Type X 4x8', 'sheathing', 'Gypsum', 'Type X', '5/8x4x8', EACH),

    # --- Subfloor & Underlayment ---
    ('Plywood 23/32 T&G 4x8 Subfloor', 'subfloor', 'Plywood', 'T&G', '23/32x4x8', EACH),
    ('OSB 23/32 T&G 4x8 Subfloor', 'subfloor', 'OSB', 'T&G', '23/32x4x8', EACH),
    ('Underlayment 1/4 4x8', 'subfloor', 'Plywood', '', '1/4x4x8', EACH),

    # --- Roofing ---
    ('Roofing Felt #15 Roll', 'roofing', '', '#15', '', EACH),
    ('Ice & Water Shield Roll', 'roofing', '', '', "3'x66'", EACH),
    ('Architectural Shingles (Bundle)', 'roofing', '', '', '', EACH),
    ('Starter Shingles (Bundle)', 'roofing', '', '', '', EACH),
    ('Hip & Ridge Shingles (Bundle)', 'roofing', '', '', '', EACH),
    ('Drip Edge 10ft', 'roofing', 'Aluminum', '', "2x2", FT, DRIP, 10),
    ('Ridge Vent 4ft', 'roofing', '', '', "4'", EACH),

    # --- Housewrap & Weather Barrier ---
    ('House Wrap 3x100 Roll', 'weather_barrier', '', '', "3'x100'", EACH),
    ('House Wrap Tape 2in', 'weather_barrier', '', '', '2in', EACH),
    ('Sill Seal 3-1/2x50 Roll', 'weather_barrier', '', '', "3.5\"x50'", EACH),
    ('Flashing Tape 4in', 'weather_barrier', '', '', '4in', EACH),

    # --- Connectors & Hardware ---
    ('Joist Hanger 2x8', 'connectors', '', '', '2x8', EACH),
    ('Joist Hanger 2x12', 'connectors', '', '', '2x12', EACH),
    ('LVL Hanger 1-3/4', 'connectors', '', '', '1.75', EACH),
    ('I-Joist Hanger', 'connectors', '', '', '', EACH),
    ('Hurricane Tie H2.5A', 'connectors', '', '', '', EACH),
    ('Post Base 4x4', 'connectors', '', '', '4x4', EACH),
    ('Post Base 6x6', 'connectors', '', '', '6x6', EACH),
    ('Post Cap 6x6', 'connectors', '', '', '6x6', EACH),
    ('Strap Tie 12in', 'connectors', '', '', '12in', EACH),
    ('Hold-Down HDU', 'connectors', '', '', '', EACH),
    ('Anchor Bolt 1/2x10', 'connectors', '', '', '1/2x10', EACH),
    ('Structural Screw 6in', 'connectors', '', '', '6in', EACH),

    # --- Fasteners & Adhesive ---
    ('Common Nails 8d (Box)', 'fasteners', '', '', '2-3/8"', BOX, 2500),
    ('Common Nails 10d (Box)', 'fasteners', '', '', '3"', BOX, 2500),
    ('Joist Hanger Nails (Box)', 'fasteners', '', '', '1-1/2"', BOX, 1000),
    ('Roofing Nails 1-1/4 (Box)', 'fasteners', '', '', '1-1/4"', BOX, 7200),
    ('Subfloor Screws 2-1/2 (Box)', 'fasteners', '', '', '2-1/2"', BOX, 800),
    ('Deck Screws 3in (Box)', 'fasteners', '', '', '3"', BOX, 350),
    ('Construction Adhesive 28oz', 'fasteners', '', '', '28oz', EACH),
    ('Subfloor Adhesive 28oz', 'fasteners', '', '', '28oz', EACH),

    # --- Decking & Railing ---
    ('5/4x6 PT Decking', 'decking', 'SYP', 'PT', '5/4x6', FT, PT_DECK, 16),
    ('2x6 PT Decking', 'decking', 'SYP', 'PT', '2x6', FT, PT_DECK, 16),
    ('Composite Decking 1x6', 'decking', 'Composite', '', '1x6', FT, [12, 16, 20], 16),
    ('Cedar Decking 5/4x6', 'decking', 'Cedar', '', '5/4x6', FT, PT_DECK, 16),
    ('Deck Railing Kit 6ft', 'decking', '', '', "6'", EACH),
    ('Deck Baluster', 'decking', '', '', '', EACH),
    ('Deck Post 4x4 PT', 'decking', 'SYP', 'PT', '4x4', FT, [8, 10, 12], 8),

    # --- Concrete & Miscellaneous ---
    ('Sonotube 8in', 'concrete_misc', '', '', '8in', EACH),
    ('Sonotube 10in', 'concrete_misc', '', '', '10in', EACH),
    ('Sonotube 12in', 'concrete_misc', '', '', '12in', EACH),
    ('Lattice Panel 4x8', 'concrete_misc', '', '', '4x8', EACH),
    ('Bulkhead Door', 'concrete_misc', '', '', '', EACH),
]


def seed(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    MaterialLength = apps.get_model('catalog', 'MaterialLength')

    # 1. Backfill categories on already-seeded global products.
    for name, category in EXISTING_CATEGORIES.items():
        MaterialProduct.objects.filter(name=name, account__isnull=True).update(category=category)

    # 2. Add the new global products (idempotent by name).
    for row in NEW_PRODUCTS:
        name, category, species, grade, dimension, input_type = row[:6]
        if MaterialProduct.objects.filter(name=name, account__isnull=True).exists():
            continue
        product = MaterialProduct.objects.create(
            name=name, slug=slugify(name), category=category, species=species,
            grade=grade, nominal_dimension=dimension, input_type=input_type,
            quantity_per_box=(row[6] if input_type == 'box' else None),
        )
        if input_type == 'ft':
            lengths, default = row[6], row[7]
            for length_ft in lengths:
                MaterialLength.objects.create(
                    product=product, length_ft=length_ft, is_default=(length_ft == default),
                )


def unseed(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    names = [row[0] for row in NEW_PRODUCTS]
    MaterialProduct.objects.filter(name__in=names, account__isnull=True).delete()
    for name in EXISTING_CATEGORIES:
        MaterialProduct.objects.filter(name=name, account__isnull=True).update(category='uncategorized')


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_materialproduct_category'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
