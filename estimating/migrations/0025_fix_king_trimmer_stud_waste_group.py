from decimal import Decimal

from django.db import migrations

# King/Trimmer studs are a fixed, exact count per opening (always ordered in
# pairs) - not a continuous run subject to cut/damage waste like the regular
# wall studs counted by per_spacing. 0021_material_groups' role-substring
# matcher ('stud' in role) lumped them into the same Exterior/Interior Studs
# groups as regular studs, which carry 5-10% waste - silently rounding a
# fixed count of 2 up to 3. Give them their own zero-waste group instead.
NEW_GROUP_NAME = 'King & Trimmer Studs'
AFFECTED_ROLES = ['King Stud', 'Trimmer Stud']


def _stud_group_name(wall_subtype):
    return {
        'exterior': 'Exterior Studs',
        'interior_bearing': 'Interior Bearing Studs',
        'interior_non_bearing': 'Interior Non-bearing Studs',
    }.get(wall_subtype, 'Exterior Studs')


def fix_king_trimmer_stud_group(apps, schema_editor):
    MaterialGroup = apps.get_model('estimating', 'MaterialGroup')
    CalculationRule = apps.get_model('estimating', 'CalculationRule')
    LineItem = apps.get_model('estimating', 'LineItem')

    new_group, _ = MaterialGroup.objects.get_or_create(
        name=NEW_GROUP_NAME,
        defaults={'default_waste_factor': Decimal('0'), 'display_order': 9},
    )

    rules = CalculationRule.objects.filter(role__in=AFFECTED_ROLES)
    rule_ids = list(rules.values_list('id', flat=True))
    rules.update(material_group=new_group)
    LineItem.objects.filter(calculation_rule_id__in=rule_ids).update(material_group=new_group)


def revert_king_trimmer_stud_group(apps, schema_editor):
    MaterialGroup = apps.get_model('estimating', 'MaterialGroup')
    CalculationRule = apps.get_model('estimating', 'CalculationRule')
    LineItem = apps.get_model('estimating', 'LineItem')

    for rule in CalculationRule.objects.filter(role__in=AFFECTED_ROLES).select_related('assembly'):
        group_name = _stud_group_name(getattr(rule.assembly, 'wall_subtype', ''))
        group = MaterialGroup.objects.filter(name=group_name).first()
        if group is not None:
            rule.material_group = group
            rule.save(update_fields=['material_group'])
            LineItem.objects.filter(calculation_rule_id=rule.id).update(material_group=group)

    MaterialGroup.objects.filter(name=NEW_GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0024_backfill_lineitem_stock_length'),
    ]

    operations = [
        migrations.RunPython(fix_king_trimmer_stud_group, revert_king_trimmer_stud_group),
    ]
