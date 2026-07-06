from django.db import migrations

FORMULAS = [
    ('Line LF', 'line_lf', 'The calibrated length of a line or opening in linear feet.'),
    ('Area SF', 'area_sqft', 'The calibrated surface area of an area trace in square feet.'),
    ('Perimeter LF', 'perimeter_lf', 'The calibrated perimeter of an area trace in linear feet.'),
    ('Count', 'count', 'The number of points in a count trace.'),
]


def seed(apps, schema_editor):
    Formula = apps.get_model('estimating', 'Formula')
    for name, measurement_kind, description in FORMULAS:
        Formula.objects.get_or_create(
            account=None,
            name=name,
            defaults={
                'measurement_kind': measurement_kind,
                'description': description,
            },
        )


def unseed(apps, schema_editor):
    Formula = apps.get_model('estimating', 'Formula')
    Formula.objects.filter(account__isnull=True, name__in=[row[0] for row in FORMULAS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('estimating', '0006_alter_calculationrule_formula_kind_formula_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
