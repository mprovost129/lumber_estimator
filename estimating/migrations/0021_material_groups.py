from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


GROUP_DEFAULTS = [
    ('Exterior Studs', Decimal('0.10')),
    ('Exterior Plates', Decimal('0.05')),
    ('Interior Bearing Studs', Decimal('0.10')),
    ('Interior Bearing Plates', Decimal('0.05')),
    ('Interior Non-bearing Studs', Decimal('0.10')),
    ('Interior Non-bearing Plates', Decimal('0.05')),
    ('Wall Sheathing', Decimal('0.10')),
    ('Wall Blocking', Decimal('0.05')),
    ('Window & Door Headers', Decimal('0.00')),
    ('Dropped Beams', Decimal('0.00')),
    ('Columns', Decimal('0.00')),
    ('Wall Hardware', Decimal('0.00')),
    ('Wall Bracing', Decimal('0.00')),
    ('Pocket Doors', Decimal('0.00')),
    ('Sill Seal / Termite Shield', Decimal('0.00')),
    ('Sill Plates', Decimal('0.05')),
    ('Foundation Hardware', Decimal('0.00')),
    ('Rim Board', Decimal('0.05')),
    ('Floor Joists', Decimal('0.05')),
    ('Floor Beams', Decimal('0.00')),
    ('Floor Blocking', Decimal('0.05')),
    ('Floor Hardware', Decimal('0.00')),
    ('Floor Sheathing', Decimal('0.10')),
    ('Floor Adhesive', Decimal('0.00')),
    ('Floor Bridging', Decimal('0.05')),
    ('Stringers', Decimal('0.00')),
    ('Treads', Decimal('0.00')),
    ('Landing Framing', Decimal('0.00')),
    ('Landing Sheathing', Decimal('0.10')),
    ('Stair Hardware', Decimal('0.00')),
    ('Ceiling Joists', Decimal('0.05')),
    ('Ceiling Beams', Decimal('0.00')),
    ('Ceiling Hardware', Decimal('0.00')),
    ('Ceiling Blocking', Decimal('0.05')),
    ('Ceiling Rim', Decimal('0.05')),
    ('Strongbacks', Decimal('0.05')),
    ('Strapping', Decimal('0.00')),
    ('Roof Rafters', Decimal('0.10')),
    ('Roof Beams', Decimal('0.00')),
    ('Ridge Boards', Decimal('0.00')),
    ('Ridge Beams', Decimal('0.00')),
    ('Hip Boards', Decimal('0.00')),
    ('Hip Beams', Decimal('0.00')),
    ('Valley Cleats', Decimal('0.05')),
    ('Valley Beams', Decimal('0.00')),
    ('Collar Ties', Decimal('0.05')),
    ('Roof Blocking', Decimal('0.05')),
    ('Roof Bracing', Decimal('0.05')),
    ('Roof Sheathing', Decimal('0.10')),
    ('Eave Sub-fascia', Decimal('0.00')),
    ('Soffit Framing', Decimal('0.05')),
    ('Rake Framing', Decimal('0.05')),
    ('Roof Hardware', Decimal('0.00')),
    ('Underlayment', Decimal('0.10')),
    ('Ice & Water Shield', Decimal('0.10')),
    ('Starter Shingles', Decimal('0.10')),
    ('Hip & Ridge', Decimal('0.10')),
    ('Roof Shingles', Decimal('0.10')),
    ('Ridge Vent', Decimal('0.00')),
    ('Drip Edge', Decimal('0.00')),
    ('Roof Flashing', Decimal('0.00')),
    ('House Wrap', Decimal('0.00')),
    ('Vinyl Siding', Decimal('0.10')),
    ('Clapboard Siding', Decimal('0.10')),
    ('Shingle Siding', Decimal('0.10')),
    ('Vertical Siding', Decimal('0.10')),
    ('Inside Corner Trim', Decimal('0.00')),
    ('Outside Corner Trim', Decimal('0.00')),
    ('Watertable Trim', Decimal('0.00')),
    ('Mid-height Band Trim', Decimal('0.00')),
    ('Window & Door Flashing', Decimal('0.00')),
    ('Window & Door Trim', Decimal('0.00')),
    ('Garage Door Trim', Decimal('0.00')),
    ('Eave Frieze Trim', Decimal('0.00')),
    ('Gable Frieze Trim', Decimal('0.00')),
    ('Eave Fascia Trim', Decimal('0.00')),
    ('Gable Fascia Trim', Decimal('0.00')),
    ('Eave Soffit Trim', Decimal('0.00')),
    ('Rake Soffit Trim', Decimal('0.00')),
    ('Shadow Board Trim', Decimal('0.00')),
    ('Panel & Molding Trim', Decimal('0.00')),
    ('Gable Vent', Decimal('0.00')),
    ('Soffit Vent', Decimal('0.00')),
    ('Column Trim', Decimal('0.00')),
    ('Beam Enclosure Trim', Decimal('0.00')),
    ('Ceiling Trim', Decimal('0.00')),
    ('Deck Joists', Decimal('0.05')),
    ('Deck Beams', Decimal('0.00')),
    ('Deck Ledger', Decimal('0.00')),
    ('Deck Rim', Decimal('0.05')),
    ('Deck Blocking', Decimal('0.05')),
    ('Deck Hardware', Decimal('0.00')),
    ('Deck Flashing', Decimal('0.00')),
    ('Decking', Decimal('0.10')),
    ('Railing System', Decimal('0.00')),
    ('Deck Stair Stringers', Decimal('0.00')),
    ('Deck Landing Framing', Decimal('0.00')),
    ('Deck Columns', Decimal('0.00')),
    ('Sonotubes', Decimal('0.00')),
    ('Deck Trim', Decimal('0.00')),
    ('Lattice', Decimal('0.00')),
    ('Bulkhead', Decimal('0.00')),
    ('Miscellaneous', Decimal('0.00')),
]


def _stud_group(wall_subtype):
    return {
        'exterior': 'Exterior Studs',
        'interior_bearing': 'Interior Bearing Studs',
        'interior_non_bearing': 'Interior Non-bearing Studs',
    }.get(wall_subtype, 'Exterior Studs')


def _plate_group(wall_subtype):
    return {
        'exterior': 'Exterior Plates',
        'interior_bearing': 'Interior Bearing Plates',
        'interior_non_bearing': 'Interior Non-bearing Plates',
    }.get(wall_subtype, 'Exterior Plates')


def _match_group(rule, material_name):
    role = (rule.role or '').strip().lower()
    material_name = (material_name or '').strip().lower()
    category = getattr(rule.assembly, 'category', '')
    wall_subtype = getattr(rule.assembly, 'wall_subtype', '')
    beam_type = getattr(rule.assembly, 'beam_type', '')

    if category == 'foundation_sill':
        if 'seal' in role or 'termite' in role:
            return 'Sill Seal / Termite Shield'
        if 'sill' in role and 'plate' in role:
            return 'Sill Plates'
        if 'hardware' in role:
            return 'Foundation Hardware'
        return 'Miscellaneous'

    if category in ('wall_system', 'openings'):
        if 'header' in role:
            return 'Window & Door Headers'
        if 'sheathing' in role:
            return 'Wall Sheathing'
        if 'block' in role:
            return 'Wall Blocking'
        if 'hardware' in role or 'hanger' in role or 'fastener' in role:
            return 'Wall Hardware'
        if 'brace' in role:
            return 'Wall Bracing'
        if 'pocket' in role:
            return 'Pocket Doors'
        if 'column' in role or 'post' in role:
            return 'Columns'
        if 'beam' in role or beam_type == 'dropped':
            return 'Dropped Beams'
        if 'plate' in role:
            return _plate_group(wall_subtype)
        if 'stud' in role:
            return _stud_group(wall_subtype)
        if 'house wrap' in material_name:
            return 'House Wrap'
        if 'siding' in material_name:
            if 'vinyl' in material_name:
                return 'Vinyl Siding'
            if 'clapboard' in material_name:
                return 'Clapboard Siding'
            if 'shingle' in material_name:
                return 'Shingle Siding'
            return 'Vertical Siding'
        return 'Miscellaneous'

    if category == 'floor_system':
        if 'rim' in role:
            return 'Rim Board'
        if 'joist' in role:
            return 'Floor Joists'
        if 'beam' in role:
            return 'Floor Beams'
        if 'block' in role:
            return 'Floor Blocking'
        if 'hardware' in role or 'hanger' in role or 'fastener' in role:
            return 'Floor Hardware'
        if 'sheathing' in role or 'subfloor' in role:
            return 'Floor Sheathing'
        if 'adhesive' in role:
            return 'Floor Adhesive'
        if 'bridg' in role:
            return 'Floor Bridging'
        return 'Miscellaneous'

    if category == 'stairs':
        if 'stringer' in role:
            return 'Stringers'
        if 'tread' in role:
            return 'Treads'
        if 'landing' in role and 'sheath' in role:
            return 'Landing Sheathing'
        if 'landing' in role:
            return 'Landing Framing'
        if 'hardware' in role:
            return 'Stair Hardware'
        return 'Miscellaneous'

    if category == 'ceiling':
        if 'joist' in role:
            return 'Ceiling Joists'
        if 'beam' in role:
            return 'Ceiling Beams'
        if 'hardware' in role:
            return 'Ceiling Hardware'
        if 'block' in role:
            return 'Ceiling Blocking'
        if 'rim' in role:
            return 'Ceiling Rim'
        if 'strongback' in role:
            return 'Strongbacks'
        if 'strap' in role:
            return 'Strapping'
        return 'Miscellaneous'

    if category == 'roof':
        if 'rafter' in role or 'truss' in role:
            return 'Roof Rafters'
        if 'ridge board' in role:
            return 'Ridge Boards'
        if 'ridge beam' in role:
            return 'Ridge Beams'
        if 'hip board' in role:
            return 'Hip Boards'
        if 'hip beam' in role:
            return 'Hip Beams'
        if 'valley cleat' in role:
            return 'Valley Cleats'
        if 'valley beam' in role:
            return 'Valley Beams'
        if 'collar' in role:
            return 'Collar Ties'
        if 'beam' in role:
            return 'Roof Beams'
        if 'block' in role:
            return 'Roof Blocking'
        if 'brace' in role:
            return 'Roof Bracing'
        if 'sheathing' in role:
            return 'Roof Sheathing'
        if 'sub-fascia' in role:
            return 'Eave Sub-fascia'
        if 'soffit' in role and 'frame' in role:
            return 'Soffit Framing'
        if 'rake' in role and 'frame' in role:
            return 'Rake Framing'
        if 'hardware' in role or 'hanger' in role or 'fastener' in role:
            return 'Roof Hardware'
        if 'felt' in material_name or 'underlayment' in role:
            return 'Underlayment'
        if 'ice' in material_name:
            return 'Ice & Water Shield'
        if 'starter' in material_name:
            return 'Starter Shingles'
        if 'hip & ridge' in material_name:
            return 'Hip & Ridge'
        if 'shingle' in material_name or 'shingle' in role:
            return 'Roof Shingles'
        if 'ridge vent' in material_name:
            return 'Ridge Vent'
        if 'drip edge' in material_name:
            return 'Drip Edge'
        if 'flashing' in role or 'flashing' in material_name:
            return 'Roof Flashing'
        return 'Miscellaneous'

    if category == 'siding_exterior':
        if 'house wrap' in material_name or 'house wrap' in role:
            return 'House Wrap'
        if 'vinyl' in material_name:
            return 'Vinyl Siding'
        if 'clapboard' in material_name:
            return 'Clapboard Siding'
        if 'shingle' in material_name:
            return 'Shingle Siding'
        if 'siding' in material_name:
            return 'Vertical Siding'
        if 'flashing' in role or 'flashing' in material_name:
            return 'Window & Door Flashing'
        if 'trim' in role or 'trim' in material_name:
            return 'Window & Door Trim'
        return 'Miscellaneous'

    if category == 'exterior_deck':
        if 'joist' in role:
            return 'Deck Joists'
        if 'beam' in role:
            return 'Deck Beams'
        if 'ledger' in role:
            return 'Deck Ledger'
        if 'rim' in role:
            return 'Deck Rim'
        if 'block' in role:
            return 'Deck Blocking'
        if 'hardware' in role or 'hanger' in role or 'fastener' in role:
            return 'Deck Hardware'
        if 'flashing' in role:
            return 'Deck Flashing'
        if 'decking' in role:
            return 'Decking'
        if 'rail' in role:
            return 'Railing System'
        if 'stringer' in role:
            return 'Deck Stair Stringers'
        if 'landing' in role:
            return 'Deck Landing Framing'
        if 'column' in role or 'post' in role:
            return 'Deck Columns'
        if 'sonotube' in role:
            return 'Sonotubes'
        if 'trim' in role:
            return 'Deck Trim'
        if 'lattice' in role:
            return 'Lattice'
        return 'Miscellaneous'

    return 'Bulkhead' if role == 'bulkhead' else 'Miscellaneous'


def seed_material_groups(apps, schema_editor):
    MaterialGroup = apps.get_model('estimating', 'MaterialGroup')
    CalculationRule = apps.get_model('estimating', 'CalculationRule')
    LineItem = apps.get_model('estimating', 'LineItem')
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')

    group_map = {}
    for index, (name, waste) in enumerate(GROUP_DEFAULTS, start=1):
        group = MaterialGroup.objects.create(
            name=name,
            default_waste_factor=waste,
            display_order=index,
        )
        group_map[name] = group

    material_names = dict(MaterialProduct.objects.values_list('id', 'name'))
    for rule in CalculationRule.objects.select_related('assembly').all():
        group_name = _match_group(rule, material_names.get(rule.material_id, ''))
        rule.material_group_id = group_map[group_name].pk
        rule.save(update_fields=['material_group'])

    for item in LineItem.objects.exclude(calculation_rule_id__isnull=True).select_related('calculation_rule'):
        if item.calculation_rule_id and item.calculation_rule.material_group_id:
            item.material_group_id = item.calculation_rule.material_group_id
            item.save(update_fields=['material_group'])


def unseed_material_groups(apps, schema_editor):
    MaterialGroup = apps.get_model('estimating', 'MaterialGroup')
    MaterialGroup.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0020_seed_default_assemblies'),
        ('projects', '0005_projecttemplate_is_favorite'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaterialGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('default_waste_factor', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=4)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={'ordering': ['display_order', 'name']},
        ),
        migrations.AddField(
            model_name='calculationrule',
            name='material_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='calculation_rules', to='estimating.materialgroup'),
        ),
        migrations.AddField(
            model_name='lineitem',
            name='material_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='line_items', to='estimating.materialgroup'),
        ),
        migrations.CreateModel(
            name='EstimateMaterialGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('waste_factor', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=4)),
                ('estimate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='material_group_settings', to='projects.estimate')),
                ('material_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='estimate_settings', to='estimating.materialgroup')),
            ],
            options={'ordering': ['estimate', 'material_group']},
        ),
        migrations.AddConstraint(
            model_name='estimatematerialgroup',
            constraint=models.UniqueConstraint(fields=('estimate', 'material_group'), name='unique_estimate_material_group_setting'),
        ),
        migrations.RunPython(seed_material_groups, unseed_material_groups),
    ]
