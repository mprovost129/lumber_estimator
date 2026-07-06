from decimal import Decimal

from django.db import migrations


def fix_rafter_multiplier_and_seed_fasteners(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    CalculationRule = apps.get_model('estimating', 'CalculationRule')
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')

    # Bug fix: standard rafter takeoff doubles for both roof planes (rafters
    # run up each side of the ridge), matching the reference formula
    # "Rafters = (ceil(length*12/spacing)+1) x planes". This assembly was
    # seeded with multiplier=1, undercounting rafters by half.
    CalculationRule.objects.filter(
        assembly__name='2x8 Roof Rafters - 16 in OC', role='Rafter',
    ).update(multiplier=2)

    # Fasteners-by-box example: the reference spec documents this as
    # "Boxes = CEILING(Total_fasteners / Per_box)" but leaves the actual
    # fastener rate to the estimator's own practice ("Estimate fasteners per
    # connection, then round to boxes"). 10 nails per linear foot of wall is
    # a rough starting placeholder, not an engineered fastener schedule -
    # tune units_per_measurement via admin to match your own practice.
    nails = MaterialProduct.objects.get(name='Framing Nails 3-1/4 (Box)', account__isnull=True)
    wall_assembly = Assembly.objects.get(name='2x6 Wall - 16 in OC', account__isnull=True)
    next_order = (
        CalculationRule.objects.filter(assembly=wall_assembly)
        .order_by('-order').values_list('order', flat=True).first() or 0
    ) + 1
    CalculationRule.objects.create(
        assembly=wall_assembly, material=nails, role='Framing Nails',
        formula_kind='per_box', units_per_measurement=Decimal('10'),
        waste_factor=Decimal('0'), order=next_order,
    )


def undo(apps, schema_editor):
    CalculationRule = apps.get_model('estimating', 'CalculationRule')
    CalculationRule.objects.filter(
        assembly__name='2x8 Roof Rafters - 16 in OC', role='Rafter',
    ).update(multiplier=1)
    CalculationRule.objects.filter(
        assembly__name='2x6 Wall - 16 in OC', role='Framing Nails',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0009_calculationrule_units_per_measurement_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_rafter_multiplier_and_seed_fasteners, undo),
    ]
