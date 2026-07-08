import math
from decimal import Decimal

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

    class Category(models.TextChoices):
        """Catalog grouping by material type, used to organize the material
        library. Distinct from a LineItem's construction-system category."""
        DIMENSIONAL = 'dimensional', 'Dimensional Lumber'
        PRESSURE_TREATED = 'pressure_treated', 'Pressure-Treated'
        STUDS = 'studs', 'Studs & Precut'
        BOARDS = 'boards', 'Boards & Trim'
        ENGINEERED = 'engineered', 'Engineered Lumber'
        SHEATHING = 'sheathing', 'Sheathing & Panels'
        SUBFLOOR = 'subfloor', 'Subfloor & Underlayment'
        ROOFING = 'roofing', 'Roofing'
        SIDING = 'siding', 'Siding & Exterior Finish'
        WEATHER_BARRIER = 'weather_barrier', 'Housewrap & Weather Barrier'
        CONNECTORS = 'connectors', 'Connectors & Hardware'
        FASTENERS = 'fasteners', 'Fasteners & Adhesive'
        DECKING = 'decking', 'Decking & Railing'
        CONCRETE_MISC = 'concrete_misc', 'Concrete & Miscellaneous'
        UNCATEGORIZED = 'uncategorized', 'Uncategorized'

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, null=True, blank=True,
        related_name='custom_materials',
        help_text='Leave blank for a global material available to every account.',
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    category = models.CharField(
        max_length=30, choices=Category.choices, default=Category.UNCATEGORIZED,
        help_text='Catalog grouping used to organize the material library.',
    )
    species = models.CharField(max_length=50, blank=True)
    grade = models.CharField(max_length=50, blank=True)
    nominal_dimension = models.CharField(max_length=20, blank=True)
    input_type = models.CharField(max_length=20, choices=InputType.choices, default=InputType.EACH)
    supported_input_types = models.JSONField(
        default=list, blank=True,
        help_text='One or more ordering methods this material supports, e.g. feet stock, per-piece, or box.',
    )
    quantity_per_box = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Used whenever Box is one of the supported input types, e.g. 100 screws per box.',
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
        self.supported_input_types = self.normalized_supported_input_types()
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def clean(self):
        supported = self.normalized_supported_input_types()
        if self.input_type not in supported:
            raise ValidationError({'input_type': 'Default input type must also be one of the supported input types.'})
        if self.InputType.BOX in supported and not self.quantity_per_box:
            raise ValidationError({'quantity_per_box': 'Required when box is a supported input type.'})
        if self.InputType.BOX not in supported and self.quantity_per_box:
            raise ValidationError({'quantity_per_box': 'Only used when box is a supported input type.'})

    def normalized_supported_input_types(self):
        raw = self.supported_input_types or []
        if isinstance(raw, str):
            raw = [raw]
        valid = {choice for choice, _ in self.InputType.choices}
        ordered = []
        for input_type in raw:
            if input_type in valid and input_type not in ordered:
                ordered.append(input_type)
        if not ordered:
            if self.input_type in valid:
                ordered = [self.input_type]
            else:
                ordered = [self.InputType.EACH]
        return ordered

    def supports_input_type(self, input_type):
        return input_type in self.normalized_supported_input_types()

    @property
    def supported_input_type_labels(self):
        labels = dict(self.InputType.choices)
        return [labels[input_type] for input_type in self.normalized_supported_input_types() if input_type in labels]

    def boxes_needed(self, quantity):
        """Number of boxes to order to cover `quantity` units. Box materials only."""
        if not self.supports_input_type(self.InputType.BOX):
            raise ValueError(f'{self} is not a box-input material.')
        return math.ceil(quantity / self.quantity_per_box)

    def stock_length_for(self, required_length_ft):
        """Smallest in-stock length that covers `required_length_ft`. Feet materials only."""
        if not self.supports_input_type(self.InputType.FT):
            raise ValueError(f'{self} is not a feet-input material.')
        length = self.lengths.filter(length_ft__gte=required_length_ft).order_by('length_ft').first()
        if length is None:
            raise ValueError(f'No stock length of {self} covers {required_length_ft} ft.')
        return length.length_ft

    @property
    def default_length_ft(self):
        """The stock length used for total-length / default-length quantity
        calculations (e.g. how many plate pieces cover a wall run). Feet materials only."""
        if not self.supports_input_type(self.InputType.FT):
            raise ValueError(f'{self} is not a feet-input material.')
        default = self.lengths.filter(is_default=True).first()
        if default is None:
            raise ValueError(f'{self} has no default stock length set.')
        return default.length_ft

    @property
    def max_length_ft(self):
        """The longest in-stock length. Feet materials only. Used to decide
        whether a member has to be spliced from more than one stock piece."""
        if not self.supports_input_type(self.InputType.FT):
            raise ValueError(f'{self} is not a feet-input material.')
        longest = self.lengths.order_by('-length_ft').first()
        if longest is None:
            raise ValueError(f'{self} has no stock lengths set.')
        return longest.length_ft

    def pieces_for_length(self, required_length_ft):
        """Stock pieces needed to build ONE member of `required_length_ft`,
        splicing end to end when it is longer than the longest stock piece.
        Returns (piece_count, piece_length_ft). Feet materials only.

        A member that fits in a single stock length returns (1, smallest
        covering length) - the same choice stock_length_for() makes. A longer
        member is built from full-length pieces of the longest stock, so it
        returns (ceil(required / max_stock), max_stock). Splice laps are not
        modeled here; cover them with the rule's waste_factor."""
        required = Decimal(str(required_length_ft))
        max_len = self.max_length_ft
        if required <= max_len:
            return 1, self.stock_length_for(required)
        return math.ceil(required / max_len), max_len


class MaterialLength(models.Model):
    """One in-stock length for an input_type=FT MaterialProduct. `is_default`
    marks the length used for total-length / default-length quantity calculations.
    The program can only ever use lengths that appear here.

    Decimal (not whole feet) so precut stud lengths - e.g. 92-5/8 in and
    104-5/8 in, the standard precuts for 8'-1-1/8" and 9'-1-1/8" wall
    heights - can be stored exactly: 92.625 in / 12 = 7.71875 ft,
    104.625 in / 12 = 8.71875 ft, both exact at 5 decimal places."""

    product = models.ForeignKey(MaterialProduct, on_delete=models.CASCADE, related_name='lengths')
    length_ft = models.DecimalField(max_digits=8, decimal_places=5)
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
        # length_ft may still be a plain int/float here (Django only coerces a
        # DecimalField to Decimal on load from the DB, not on assignment), so
        # go through Decimal(str(...)) before .normalize() (which strips
        # trailing zeros - 7.71875 stays exact, 10.00000 -> 10 - but can render
        # round numbers in scientific notation, e.g. 10 -> '1E+1', hence the
        # format(..., 'f') to force fixed-point instead of str()/f-string).
        length = Decimal(str(self.length_ft)).normalize()
        return f'{self.product.name} - {format(length, "f")} ft'

    def clean(self):
        if self.product_id and not self.product.supports_input_type(MaterialProduct.InputType.FT):
            raise ValidationError('Stock lengths can only be added to feet-input materials.')


class MaterialPrice(models.Model):
    """A per-account unit cost for a material, so quantities can roll up to a
    bid total. Account-scoped on purpose: pricing is a contractor's private
    edge (lumber costs swing weekly and vary by yard), and keeping it separate
    from MaterialProduct means the shared global catalog is never touched when
    someone prices a stock SKU. Missing prices are first-class: the estimate
    stays a valid material list with zero prices set, matching the product's
    core promise."""

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='material_prices',
    )
    material = models.ForeignKey(
        MaterialProduct, on_delete=models.CASCADE, related_name='prices',
    )
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Cost per ordering unit: per stock piece for feet materials, '
                  'per box for box materials, per each otherwise.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'material'], name='unique_price_per_account_material'),
        ]

    def __str__(self):
        return f'{self.material.name}: {self.unit_cost}'
