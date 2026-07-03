import math

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from accounts.models import Account


class MaterialProductQuerySet(models.QuerySet):
    def visible_to(self, account):
        return self.filter(models.Q(account__isnull=True) | models.Q(account=account))


class MaterialProduct(models.Model):
    """A catalog entry, e.g. '2x6 SPF #2' or 'Deck screws 3in'. Global when
    `account` is blank (staff-managed, visible to everyone); an Account can
    also have its own custom materials, visible only to that Account."""

    class InputType(models.TextChoices):
        FT = 'ft', 'Feet (stock lengths)'
        BOX = 'box', 'Box'
        EACH = 'each', 'Each'

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, null=True, blank=True,
        related_name='custom_materials',
        help_text='Leave blank for a global material available to every account.',
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    species = models.CharField(max_length=50, blank=True)
    grade = models.CharField(max_length=50, blank=True)
    nominal_dimension = models.CharField(max_length=20, blank=True)
    input_type = models.CharField(max_length=20, choices=InputType.choices, default=InputType.EACH)
    quantity_per_box = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Only used when input type is Box, e.g. 100 screws per box.',
    )

    objects = MaterialProductQuerySet.as_manager()

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['slug'], condition=models.Q(account__isnull=True),
                name='unique_global_material_slug',
            ),
            models.UniqueConstraint(
                fields=['account', 'slug'], condition=models.Q(account__isnull=False),
                name='unique_account_material_slug',
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def clean(self):
        if self.input_type == self.InputType.BOX and not self.quantity_per_box:
            raise ValidationError({'quantity_per_box': 'Required when input type is Box.'})
        if self.input_type != self.InputType.BOX and self.quantity_per_box:
            raise ValidationError({'quantity_per_box': 'Only used when input type is Box.'})

    def boxes_needed(self, quantity):
        """Number of boxes to order to cover `quantity` units. Box materials only."""
        if self.input_type != self.InputType.BOX:
            raise ValueError(f'{self} is not a box-input material.')
        return math.ceil(quantity / self.quantity_per_box)

    def stock_length_for(self, required_length_ft):
        """Smallest in-stock length that covers `required_length_ft`. Feet materials only."""
        if self.input_type != self.InputType.FT:
            raise ValueError(f'{self} is not a feet-input material.')
        length = self.lengths.filter(length_ft__gte=required_length_ft).order_by('length_ft').first()
        if length is None:
            raise ValueError(f'No stock length of {self} covers {required_length_ft} ft.')
        return length.length_ft


class MaterialLength(models.Model):
    """One in-stock length for an input_type=FT MaterialProduct. `is_default`
    marks the length used for total-length / default-length quantity calculations.
    The program can only ever use lengths that appear here."""

    product = models.ForeignKey(MaterialProduct, on_delete=models.CASCADE, related_name='lengths')
    length_ft = models.PositiveSmallIntegerField()
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['product', 'length_ft']
        constraints = [
            models.UniqueConstraint(fields=['product', 'length_ft'], name='unique_product_length'),
            models.UniqueConstraint(
                fields=['product'], condition=models.Q(is_default=True),
                name='unique_default_length_per_product',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} - {self.length_ft} ft'

    def clean(self):
        if self.product_id and self.product.input_type != MaterialProduct.InputType.FT:
            raise ValidationError('Stock lengths can only be added to feet-input materials.')
