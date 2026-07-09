from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from plans.models import Trace


class AssemblyQuerySet(models.QuerySet):
    def visible_to(self, account):
        return self.filter(models.Q(account__isnull=True) | models.Q(account=account))


class FormulaQuerySet(models.QuerySet):
    def visible_to(self, account):
        return self.filter(models.Q(account__isnull=True) | models.Q(account=account))


class Formula(models.Model):
    """A reusable scalar formula based on a measurement produced by a trace."""

    class MeasurementKind(models.TextChoices):
        LINE_LF = 'line_lf', 'Line length (LF)'
        AREA_SQFT = 'area_sqft', 'Area (SF)'
        PERIMETER_LF = 'perimeter_lf', 'Perimeter (LF)'
        COUNT = 'count', 'Count'

    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE, null=True, blank=True,
        related_name='custom_formulas',
        help_text='Leave blank for a stock formula available to every account.',
    )
    name = models.CharField(max_length=255)
    measurement_kind = models.CharField(max_length=20, choices=MeasurementKind.choices)
    base_formula = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='derived_formulas',
        help_text='Optional formula to build on. Account formulas can derive from stock formulas.',
    )
    multiplier = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('1'))
    addend = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0'))
    description = models.TextField(blank=True)

    objects = FormulaQuerySet.as_manager()

    class Meta:
        ordering = ['measurement_kind', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['name'], condition=models.Q(account__isnull=True),
                name='unique_global_formula_name',
            ),
            models.UniqueConstraint(
                fields=['account', 'name'], condition=models.Q(account__isnull=False),
                name='unique_account_formula_name',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.base_formula_id:
            if self.base_formula_id == self.pk:
                raise ValidationError({'base_formula': 'A formula cannot build on itself.'})
            if self.base_formula.measurement_kind != self.measurement_kind:
                raise ValidationError({'base_formula': 'Base and derived formulas must use the same measurement.'})
            if self.account_id and self.base_formula.account_id not in (None, self.account_id):
                raise ValidationError({'base_formula': 'The base formula is not available to this account.'})

    @property
    def expression(self):
        base = self.base_formula.name if self.base_formula_id else self.get_measurement_kind_display()
        expression = base
        if self.multiplier != 1:
            expression += f' × {self.multiplier.normalize()}'
        if self.addend:
            sign = '+' if self.addend > 0 else '−'
            expression += f' {sign} {abs(self.addend).normalize()}'
        return expression

    def evaluate(self, measurement):
        if self.base_formula_id:
            value = self.base_formula.evaluate(measurement)
        else:
            keys = {
                self.MeasurementKind.LINE_LF: 'length_ft',
                self.MeasurementKind.AREA_SQFT: 'area_sqft',
                self.MeasurementKind.PERIMETER_LF: 'perimeter_ft',
                self.MeasurementKind.COUNT: 'count',
            }
            value = Decimal(str(measurement[keys[self.measurement_kind]]))
        return (value * self.multiplier) + self.addend

    @property
    def supported_tool_types(self):
        return {
            self.MeasurementKind.LINE_LF: {
                Trace.ToolType.LINE, Trace.ToolType.POLYLINE, Trace.ToolType.OPENING,
            },
            self.MeasurementKind.AREA_SQFT: {Trace.ToolType.AREA, Trace.ToolType.POLYLINE},
            self.MeasurementKind.PERIMETER_LF: {Trace.ToolType.AREA, Trace.ToolType.POLYLINE},
            self.MeasurementKind.COUNT: {Trace.ToolType.COUNT},
        }[self.measurement_kind]


class Assembly(models.Model):
    """A named, reusable bundle of CalculationRules applied together to one
    Trace measurement (e.g. "2x6 Wall - 16 in OC" bundles a stud rule + top
    plate rule + bottom plate rule). Global when `account` is blank
    (staff-managed); an Account can also have its own custom assemblies."""

    class Category(models.TextChoices):
        """Construction system, matching docs/Lumber Estimator Takeoff.docx's
        build-order structure. This declaration order is the default material
        list group order (Assembly.Category.values), overridden per-account
        by Account.category_order once a user drags a section."""
        FOUNDATION_SILL = 'foundation_sill', 'Foundation & Sill'
        FLOOR_SYSTEM = 'floor_system', 'Floor System'
        WALL_SYSTEM = 'wall_system', 'Wall System'
        OPENINGS = 'openings', 'Openings'
        STAIRS = 'stairs', 'Stairs'
        CEILING = 'ceiling', 'Ceiling'
        ROOF = 'roof', 'Roof'
        SIDING_EXTERIOR = 'siding_exterior', 'Siding & Exterior Trim'
        EXTERIOR_DECK = 'exterior_deck', 'Exterior Deck'
        MISC = 'misc', 'Miscellaneous'

    class WallSubtype(models.TextChoices):
        EXTERIOR = 'exterior', 'Exterior'
        INTERIOR_BEARING = 'interior_bearing', 'Interior Bearing'
        INTERIOR_NON_BEARING = 'interior_non_bearing', 'Interior Non-Bearing'

    class OpeningKind(models.TextChoices):
        WINDOW = 'window', 'Window'
        DOOR = 'door', 'Door'

    class BeamType(models.TextChoices):
        FLUSH = 'flush', 'Flush'
        DROPPED = 'dropped', 'Dropped'

    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE, null=True, blank=True,
        related_name='custom_assemblies',
        help_text='Leave blank for a global assembly available to every account.',
    )
    name = models.CharField(max_length=255)
    tool_type = models.CharField(max_length=20, choices=Trace.ToolType.choices)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.MISC,
        help_text='Construction system this assembly belongs to, for grouping the material list.',
    )
    wall_subtype = models.CharField(
        max_length=25, choices=WallSubtype.choices, null=True, blank=True,
        help_text=(
            'Dual-purpose: for a WALL assembly (tool_type line/polyline), the wall type it represents. '
            'For an OPENING assembly (tool_type opening), the wall type its header/king/jack sizing is '
            "designed for - matched against the host wall Trace.parent_wall points to, so a window/door's "
            'materials can be auto-resolved from whichever wall it gets attached to.'
        ),
    )
    opening_kind = models.CharField(
        max_length=10, choices=OpeningKind.choices, null=True, blank=True,
        help_text='OPENING assemblies only: window or door, matched against the attached Trace.settings.opening_type.',
    )
    beam_type = models.CharField(
        max_length=10, choices=BeamType.choices, null=True, blank=True,
        help_text='Flush (within floor/ceiling depth) or dropped (hangs below) - classification only for now.',
    )
    description = models.TextField(blank=True)
    is_default = models.BooleanField(
        default=False,
        help_text=(
            'Auto-selected in the plan viewer when its tool/variant is picked, so drawing '
            'produces a material list without opening the assembly dropdown. Seed at most one '
            'default per tool-variant group (e.g. one exterior-wall default).'
        ),
    )

    objects = AssemblyQuerySet.as_manager()

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tool_type', 'name'], condition=models.Q(account__isnull=True),
                name='unique_global_assembly_name_per_tool_type',
            ),
            models.UniqueConstraint(
                fields=['account', 'tool_type', 'name'], condition=models.Q(account__isnull=False),
                name='unique_account_assembly_name_per_tool_type',
            ),
            models.UniqueConstraint(
                fields=['opening_kind', 'wall_subtype'],
                condition=models.Q(account__isnull=True, opening_kind__isnull=False, wall_subtype__isnull=False),
                name='unique_global_opening_kind_wall_subtype',
            ),
            models.UniqueConstraint(
                fields=['account', 'opening_kind', 'wall_subtype'],
                condition=models.Q(account__isnull=False, opening_kind__isnull=False, wall_subtype__isnull=False),
                name='unique_account_opening_kind_wall_subtype',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.wall_subtype and self.beam_type:
            raise ValidationError('An assembly cannot be both a wall/opening subtype and a beam type.')
        if self.opening_kind and self.tool_type != Trace.ToolType.OPENING:
            raise ValidationError({'opening_kind': 'Only opening-tool_type assemblies can set opening_kind.'})


class MaterialGroup(models.Model):
    """Reusable estimator-facing grouping bucket used across systems/floors."""

    name = models.CharField(max_length=100, unique=True)
    default_waste_factor = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal('0'))
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class CalculationRule(models.Model):
    """One formula within an Assembly: a material + how to convert a measured
    length into a quantity of that material."""

    class FormulaKind(models.TextChoices):
        # Line-measured (length_ft)
        PER_SPACING = 'per_spacing', 'Count by spacing along a line (e.g. studs)'
        PER_STOCK_LENGTH = 'per_stock_length', 'Count by stock length along a run (e.g. plates, rim board)'
        PER_LENGTH = 'per_length', 'Piece(s) cut to the traced length (e.g. a beam)'
        PER_LENGTH_SPLICED = 'per_length_spliced', 'Piece(s) cut to length, spliced from stock when over-length (e.g. a long built-up beam)'
        # Area-measured (area_sqft / perimeter_ft / bbox)
        PER_AREA_SPACING = 'per_area_spacing', 'Members across an area by spacing (e.g. joists, rafters, trusses)'
        PER_AREA_SPACING_SPLICED = 'per_area_spacing_spliced', 'Members across an area by spacing, each spliced from stock when over-length'
        PER_AREA_COVERAGE = 'per_area_coverage', 'Units by coverage area (e.g. sheathing sheets, felt rolls)'
        # Count-measured
        PER_COUNT = 'per_count', 'Per counted point (e.g. posts, hangers)'
        # Opening-measured (length_ft = opening width)
        HEADER = 'header', 'Header sized to the opening width'
        # Any measurement
        FIXED_COUNT = 'fixed_count', 'Fixed count per trace (e.g. king studs, trimmers)'
        PER_BOX = 'per_box', 'Boxes from an estimated per-unit rate (e.g. fasteners)'

    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE, related_name='rules')
    formula = models.ForeignKey(
        Formula, on_delete=models.PROTECT, null=True, blank=True,
        related_name='calculation_rules',
        help_text='Reusable library formula. Leave blank to use a framing formula kind.',
    )
    material = models.ForeignKey(
        'catalog.MaterialProduct', on_delete=models.PROTECT, related_name='calculation_rules',
    )
    material_group = models.ForeignKey(
        MaterialGroup, on_delete=models.PROTECT, null=True, blank=True, related_name='calculation_rules',
    )
    role = models.CharField(max_length=100, help_text='e.g. "Stud", "Top Plate", "Bottom Plate" - shown on the BOM.')
    formula_kind = models.CharField(max_length=30, choices=FormulaKind.choices, blank=True)
    multiplier = models.PositiveSmallIntegerField(
        default=1, help_text='PER_STOCK_LENGTH: e.g. 2 for a double top plate.',
    )
    extra = models.IntegerField(default=0, help_text='PER_SPACING / PER_AREA_SPACING: e.g. +1 for the end member.')
    coverage_sqft = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='PER_AREA_COVERAGE: square feet one unit covers, e.g. 32 for a 4x8 sheet.',
    )
    units_per_measurement = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text=(
            'PER_BOX: estimated units of the material (e.g. fasteners) consumed per foot/sqft/count '
            'of the trace measurement - a starting estimate to tune to your own practice, not an '
            'engineered fastener schedule.'
        ),
    )
    corner_stud_count = models.PositiveSmallIntegerField(
        default=1,
        help_text=(
            'PER_SPACING: extra studs added per corner OCCURRENCE this wall participates in - its own '
            'polyline bend (counted twice, matching two separate walls meeting end-to-end) or meeting '
            'another wall end-to-end (counted once) - a starting estimate, tune to your framing convention.'
        ),
    )
    t_intersection_stud_count = models.PositiveSmallIntegerField(
        default=1,
        help_text=(
            "PER_SPACING: extra studs where THIS wall's end butts into another wall's span "
            '(the partition side of a T-intersection).'
        ),
    )
    t_backer_stud_count = models.PositiveSmallIntegerField(
        default=1,
        help_text=(
            "PER_SPACING: extra backer/nailer studs where ANOTHER wall's end butts into THIS wall's span "
            '(the through-wall side of a T-intersection).'
        ),
    )
    waste_factor = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal('0'))
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['assembly', 'order']

    def __str__(self):
        return f'{self.assembly.name} - {self.role}'

    def clean(self):
        if bool(self.formula_id) == bool(self.formula_kind):
            raise ValidationError('Choose either a library formula or a framing formula kind.')
        if self.formula_id:
            assembly_account_id = self.assembly.account_id
            if self.formula.account_id not in (None, assembly_account_id):
                raise ValidationError({'formula': 'This formula is not available to the assembly account.'})
            if self.assembly.tool_type not in self.formula.supported_tool_types:
                raise ValidationError({'formula': 'This formula does not support the assembly tool type.'})


class LineItem(models.Model):
    """One computed (or manually added) material quantity on an Estimate."""

    class Source(models.TextChoices):
        TOOL = 'tool', 'Tool'
        MANUAL = 'manual', 'Manual'

    estimate = models.ForeignKey('projects.Estimate', on_delete=models.CASCADE, related_name='line_items')
    trace = models.ForeignKey(
        Trace, on_delete=models.CASCADE, null=True, blank=True, related_name='line_items',
    )
    calculation_rule = models.ForeignKey(
        CalculationRule, on_delete=models.SET_NULL, null=True, blank=True, related_name='line_items',
    )
    material = models.ForeignKey(
        'catalog.MaterialProduct', on_delete=models.PROTECT, related_name='line_items',
    )
    material_group = models.ForeignKey(
        MaterialGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='line_items',
    )
    role = models.CharField(max_length=100, blank=True)
    category = models.CharField(
        max_length=20, choices=Assembly.Category.choices, default=Assembly.Category.MISC,
        help_text=(
            'Construction system for grouping the material list. Set from the assembly at '
            'generation time for tool-sourced lines; chosen directly for manual ones. Denormalized '
            'rather than derived live, since calculation_rule is nullable (SET_NULL) and manual '
            'lines have no rule/assembly at all - read via Coalesce(calculation_rule__assembly__'
            'category, category) wherever grouping/order needs to reflect a later assembly edit.'
        ),
    )
    length_ft = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    waste_factor = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal('0'))
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['role', 'material__name']

    def __str__(self):
        return f'{self.quantity} x {self.material.name} ({self.role})'


class EstimateMaterialGroup(models.Model):
    """Estimate-specific waste override for a reusable material group."""

    estimate = models.ForeignKey('projects.Estimate', on_delete=models.CASCADE, related_name='material_group_settings')
    material_group = models.ForeignKey(MaterialGroup, on_delete=models.CASCADE, related_name='estimate_settings')
    waste_factor = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal('0'))

    class Meta:
        ordering = ['estimate', 'material_group']
        constraints = [
            models.UniqueConstraint(
                fields=['estimate', 'material_group'],
                name='unique_estimate_material_group_setting',
            ),
        ]

    def __str__(self):
        return f'{self.estimate_id}: {self.material_group.name} ({self.waste_factor})'
