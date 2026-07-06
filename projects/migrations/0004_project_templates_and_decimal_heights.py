from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


def seed_project_templates(apps, schema_editor):
    ProjectTemplate = apps.get_model('projects', 'ProjectTemplate')

    templates = [
        {
            'name': '1-Story Ranch, 9 ft 1-1/8 in',
            'description': 'Single-floor ranch with a 9 ft 1-1/8 in first-floor wall height.',
            'sort_order': 10,
            'num_floors': 1,
            'foundation_type': 'slab',
            'first_floor_wall_height_in': Decimal('109.125'),
            'stud_spacing_in': 16,
            'roof_framing': 'trusses',
        },
        {
            'name': '1-Story Ranch, 8 ft 1-1/8 in',
            'description': 'Single-floor ranch with a 8 ft 1-1/8 in first-floor wall height.',
            'sort_order': 20,
            'num_floors': 1,
            'foundation_type': 'slab',
            'first_floor_wall_height_in': Decimal('97.125'),
            'stud_spacing_in': 16,
            'roof_framing': 'trusses',
        },
        {
            'name': 'Colonial, 8 ft 1-1/8 in Both Floors',
            'description': 'Two-story colonial with 8 ft 1-1/8 in walls on both floors.',
            'sort_order': 30,
            'num_floors': 2,
            'foundation_type': 'slab',
            'first_floor_wall_height_in': Decimal('97.125'),
            'second_floor_wall_height_in': Decimal('97.125'),
            'stud_spacing_in': 16,
            'roof_framing': 'trusses',
        },
        {
            'name': 'Colonial, 9 ft 1-1/8 in First, 8 ft 1-1/8 in Second',
            'description': 'Two-story colonial with a taller first floor and standard second floor.',
            'sort_order': 40,
            'num_floors': 2,
            'foundation_type': 'slab',
            'first_floor_wall_height_in': Decimal('109.125'),
            'second_floor_wall_height_in': Decimal('97.125'),
            'stud_spacing_in': 16,
            'roof_framing': 'trusses',
        },
    ]
    for template in templates:
        ProjectTemplate.objects.update_or_create(
            account=None,
            name=template['name'],
            defaults=template,
        )


def unseed_project_templates(apps, schema_editor):
    ProjectTemplate = apps.get_model('projects', 'ProjectTemplate')
    ProjectTemplate.objects.filter(
        account__isnull=True,
        name__in=[
            '1-Story Ranch, 9 ft 1-1/8 in',
            '1-Story Ranch, 8 ft 1-1/8 in',
            'Colonial, 8 ft 1-1/8 in Both Floors',
            'Colonial, 9 ft 1-1/8 in First, 8 ft 1-1/8 in Second',
        ],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_layout_preferences'),
        ('projects', '0003_add_roof_pitch_and_siding'),
    ]

    operations = [
        migrations.AlterField(
            model_name='jobsettings',
            name='basement_wall_height_in',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
        ),
        migrations.AlterField(
            model_name='jobsettings',
            name='first_floor_wall_height_in',
            field=models.DecimalField(decimal_places=3, default=Decimal('109.125'), max_digits=6),
        ),
        migrations.AlterField(
            model_name='jobsettings',
            name='second_floor_wall_height_in',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
        ),
        migrations.CreateModel(
            name='ProjectTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('sort_order', models.PositiveSmallIntegerField(default=100)),
                ('num_floors', models.PositiveSmallIntegerField(default=1)),
                ('foundation_type', models.CharField(choices=[('slab', 'Slab on grade'), ('crawl_space', 'Crawl space'), ('full_basement', 'Full basement')], default='slab', max_length=20)),
                ('basement_wall_height_in', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ('first_floor_wall_height_in', models.DecimalField(decimal_places=3, default=Decimal('109.125'), max_digits=6)),
                ('second_floor_wall_height_in', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ('stud_spacing_in', models.PositiveSmallIntegerField(choices=[(16, '16" OC'), (24, '24" OC')], default=16)),
                ('roof_framing', models.CharField(choices=[('rafters', 'Rafters'), ('trusses', 'Trusses'), ('both', 'Both')], default='trusses', max_length=20)),
                ('roof_pitch_rise_per_12', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('floor_material', models.CharField(blank=True, max_length=255)),
                ('siding_material', models.CharField(blank=True, max_length=255)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='project_templates', to='accounts.account')),
            ],
            options={
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='projecttemplate',
            constraint=models.UniqueConstraint(fields=('account', 'name'), name='unique_project_template_name_per_account'),
        ),
        migrations.RunPython(seed_project_templates, unseed_project_templates),
    ]
