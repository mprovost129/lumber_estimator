from django.db import migrations

# One default per tool-variant group, so picking a semantic tool in the viewer
# auto-loads a working assembly. Kept unambiguous: within any candidate set the
# viewer filters to, exactly one of these is marked default.
#   Wall  -> filtered by wall_subtype
#   Beam  -> filtered by beam_type
#   Opening -> filtered by opening_kind (fallback; openings usually auto-resolve
#              from the wall they are attached to)
#   Joist -> filtered to floor/ceiling/roof area assemblies
#   Column -> the single default among count assemblies
DEFAULT_ASSEMBLY_NAMES = [
    '2x6 Exterior Wall on Slab - 16 in OC',
    '2x6 Interior Bearing Wall - 16 in OC',
    '2x4 Interior Non-Bearing Wall - 16 in OC',
    'LVL Beam - Flush (Double 1-3/4x11-7/8)',
    'LVL Beam - Dropped (Double 1-3/4x11-7/8)',
    'Window Opening - Exterior Wall Header',
    'Door Opening - Exterior Wall Header',
    '2x10 Floor Joists - 16 in OC',
    '4x4 PT Post',
]


def mark_defaults(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    Assembly.objects.filter(name__in=DEFAULT_ASSEMBLY_NAMES, account__isnull=True).update(is_default=True)


def unmark_defaults(apps, schema_editor):
    Assembly = apps.get_model('estimating', 'Assembly')
    Assembly.objects.filter(name__in=DEFAULT_ASSEMBLY_NAMES, account__isnull=True).update(is_default=False)


class Migration(migrations.Migration):

    dependencies = [
        ('estimating', '0019_assembly_is_default'),
    ]

    operations = [
        migrations.RunPython(mark_defaults, unmark_defaults),
    ]
