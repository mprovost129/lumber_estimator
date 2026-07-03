import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs_and_fix_seed_input_type(apps, schema_editor):
    MaterialProduct = apps.get_model('catalog', 'MaterialProduct')
    for product in MaterialProduct.objects.all():
        product.slug = slugify(product.name)
        # The launch SPF dimensional lumber was seeded with stock lengths;
        # that means "ft" input type under the new model, not "each".
        if product.lengths.exists():
            product.input_type = 'ft'
        product.save(update_fields=['slug', 'input_type'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('catalog', '0002_seed_dimensional_lumber'),
    ]

    operations = [
        migrations.AddField(
            model_name='materialproduct',
            name='account',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='custom_materials', to='accounts.account',
                help_text='Leave blank for a global material available to every account.',
            ),
        ),
        migrations.AddField(
            model_name='materialproduct',
            name='slug',
            field=models.SlugField(blank=True, max_length=255, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='materialproduct',
            name='quantity_per_box',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Only used when input type is Box, e.g. 100 screws per box.',
            ),
        ),
        migrations.RenameField(
            model_name='materialproduct',
            old_name='sale_unit',
            new_name='input_type',
        ),
        migrations.AlterField(
            model_name='materialproduct',
            name='input_type',
            field=models.CharField(
                choices=[('ft', 'Feet (stock lengths)'), ('box', 'Box'), ('each', 'Each')],
                default='each', max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='materialproduct',
            name='species',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='materialproduct',
            name='grade',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='materialproduct',
            name='name',
            field=models.CharField(max_length=255),
        ),
        migrations.RunPython(populate_slugs_and_fix_seed_input_type, noop),
        migrations.AddConstraint(
            model_name='materialproduct',
            constraint=models.UniqueConstraint(
                condition=models.Q(('account__isnull', True)), fields=('slug',),
                name='unique_global_material_slug',
            ),
        ),
        migrations.AddConstraint(
            model_name='materialproduct',
            constraint=models.UniqueConstraint(
                condition=models.Q(('account__isnull', False)), fields=('account', 'slug'),
                name='unique_account_material_slug',
            ),
        ),
    ]
