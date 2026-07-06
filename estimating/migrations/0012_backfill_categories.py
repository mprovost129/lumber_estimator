from django.db import migrations

# Best-guess mapping from a known global Assembly's name to its construction
# system, per docs/Lumber Estimator Takeoff.docx. A starting default, tune
# via the now-categorized Assembly edit form - same "starting estimate to
# adjust to your own practice" precedent already set for the per_box
# fastener rate (see 0010_fix_rafters_and_seed_fasteners.py).
ASSEMBLY_CATEGORY_BY_NAME = {
    '2x4 Wall - 16 in OC': 'wall_system',
    '2x6 Wall - 16 in OC': 'wall_system',
    '2x6 Exterior Wall on Slab - 16 in OC': 'wall_system',
    'LVL Beam 1-3/4x11-7/8 (Double)': 'wall_system',
    'Wall Sheathing - 7/16 OSB + House Wrap': 'wall_system',
    '4x4 PT Post': 'wall_system',
    '2x10 Floor Joists - 16 in OC': 'floor_system',
    'Joist Hangers 2x10': 'floor_system',
    '2x8 Roof Rafters - 16 in OC': 'roof',
    'Roof Trusses - 24 in OC': 'roof',
    'Window/Door Opening - 2x10 Header (2x6 Wall)': 'openings',
}


def backfill_categories(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    LineItem = apps.get_model('estimating', 'LineItem')

    for name, category in ASSEMBLY_CATEGORY_BY_NAME.items():
        Assembly.objects.filter(name=name, account__isnull=True).update(category=category)

    # Existing LineItems generated before this migration have no category yet
    # (model default 'misc'); pull the real value from their rule's assembly
    # where that link still exists. Manual/orphaned rows are left at 'misc'.
    for line_item in LineItem.objects.filter(calculation_rule__isnull=False).select_related(
        'calculation_rule__assembly',
    ):
        category = line_item.calculation_rule.assembly.category
        if category != line_item.category:
            line_item.category = category
            line_item.save(update_fields=['category'])


def undo(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    LineItem = apps.get_model('estimating', 'LineItem')
    Assembly.objects.filter(name__in=ASSEMBLY_CATEGORY_BY_NAME, account__isnull=True).update(category='misc')
    LineItem.objects.update(category='misc')


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0011_add_category'),
    ]

    operations = [
        migrations.RunPython(backfill_categories, undo),
    ]
