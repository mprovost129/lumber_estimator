from django.core.validators import RegexValidator
from django.db import models

color_validator = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message='Enter a color as a six-digit hex value, e.g. #0d6efd.',
)


class PlanQuerySet(models.QuerySet):
    def for_account(self, account):
        return self.filter(project__account=account)


class PlanPageQuerySet(models.QuerySet):
    def for_account(self, account):
        return self.filter(plan__project__account=account)


class TraceQuerySet(models.QuerySet):
    def for_account(self, account):
        return self.filter(plan_page__plan__project__account=account)


class Plan(models.Model):
    """An uploaded plan document (PDF or image), split into PlanPages on upload."""

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='plans')
    original_file = models.FileField(upload_to='plans/source/%Y/%m/')
    name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    objects = PlanQuerySet.as_manager()

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name or self.original_file.name

    def save(self, *args, **kwargs):
        if not self.name and self.original_file:
            self.name = self.original_file.name.rsplit('/', 1)[-1]
        super().save(*args, **kwargs)


class PlanPage(models.Model):
    """One rasterized page of a Plan, labeled by the user (e.g. 'First Floor')."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='pages')
    page_number = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to='plans/pages/%Y/%m/')
    thumbnail = models.ImageField(upload_to='plans/thumbnails/%Y/%m/')
    scale_pixels_per_foot = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text='Set by the Calibrate tool. Null means this page has not been calibrated yet.',
    )

    objects = PlanPageQuerySet.as_manager()

    class Meta:
        ordering = ['plan', 'page_number']
        constraints = [
            models.UniqueConstraint(fields=['plan', 'page_number'], name='unique_plan_page_number'),
        ]

    def __str__(self):
        return self.label or f'{self.plan} - page {self.page_number}'

    @property
    def display_label(self):
        return self.label or f'Page {self.page_number}'


class Trace(models.Model):
    """One user-drawn shape on a PlanPage, with a material + settings snapshot
    captured at creation time. Later changes to a tool's settings panel must
    never retroactively change an already-drawn Trace."""

    class ToolType(models.TextChoices):
        LINE = 'line', 'Line (Wall)'
        POLYLINE = 'polyline', 'Polyline / Polygon'
        AREA = 'area', 'Area (Floor / Roof / Sheathing)'
        COUNT = 'count', 'Count (Posts / Hardware)'
        OPENING = 'opening', 'Opening (Window / Door)'

    plan_page = models.ForeignKey(PlanPage, on_delete=models.CASCADE, related_name='traces')
    tool_type = models.CharField(max_length=20, choices=ToolType.choices)
    geometry = models.JSONField()
    material = models.ForeignKey(
        'catalog.MaterialProduct', on_delete=models.PROTECT, null=True, blank=True, related_name='traces',
    )
    assembly = models.ForeignKey(
        'estimating.Assembly', on_delete=models.PROTECT, null=True, blank=True, related_name='traces',
        help_text='When set, the calculation engine generates LineItems from this Trace.',
    )
    parent_wall = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='attached_openings',
        help_text='For opening traces: the wall this window/door is cut into.',
    )
    settings = models.JSONField(default=dict, blank=True)
    color = models.CharField(
        max_length=7, blank=True, validators=[color_validator],
        help_text='Optional display color in #RRGGBB format.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TraceQuerySet.as_manager()

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_tool_type_display()} trace on {self.plan_page}'


class ToolPreset(models.Model):
    """A saved tool + material + settings combo an account can reuse across projects."""

    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, related_name='tool_presets')
    name = models.CharField(max_length=255)
    tool_type = models.CharField(max_length=20, choices=Trace.ToolType.choices)
    material = models.ForeignKey(
        'catalog.MaterialProduct', on_delete=models.SET_NULL, null=True, blank=True, related_name='tool_presets',
    )
    settings = models.JSONField(default=dict, blank=True)
    color = models.CharField(
        max_length=7, blank=True, validators=[color_validator],
        help_text='Optional display color in #RRGGBB format.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'tool_type', 'name'], name='unique_preset_name_per_account_tool',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_tool_type_display()})'
