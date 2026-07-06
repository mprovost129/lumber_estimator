from decimal import Decimal

from django.db import migrations


def seed_wall_assembly(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    CalculationRule = apps.get_model('estimating', 'CalculationRule')
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')

    stud = MaterialProduct.objects.get(name='2x6 SPF #2', account__isnull=True)

    assembly = Assembly.objects.create(
        name='2x6 Wall - 16 in OC',
        tool_type='line',
        description='Exterior/interior 2x6 stud wall, 16" OC, single bottom plate, double top plate.',
    )
    CalculationRule.objects.create(
        assembly=assembly, material=stud, role='Stud', formula_kind='per_spacing',
        extra=1, waste_factor=Decimal('0.10'), order=1,
    )
    CalculationRule.objects.create(
        assembly=assembly, material=stud, role='Top Plate', formula_kind='per_stock_length',
        multiplier=2, waste_factor=Decimal('0.05'), order=2,
    )
    CalculationRule.objects.create(
        assembly=assembly, material=stud, role='Bottom Plate', formula_kind='per_stock_length',
        multiplier=1, waste_factor=Decimal('0.05'), order=3,
    )


def unseed_wall_assembly(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    Assembly.objects.filter(name='2x6 Wall - 16 in OC', account__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0001_initial'),
        ('catalog', '0003_material_input_types'),
    ]

    operations = [
        migrations.RunPython(seed_wall_assembly, unseed_wall_assembly),
    ]
