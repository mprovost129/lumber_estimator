from decimal import Decimal

from django.db import models
from django.urls import reverse

from accounts.models import Account, AccountScopedManager


class Project(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ARCHIVED = 'archived', 'Archived'

    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='projects')
    name = models.CharField(max_length=255)
    client = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AccountScopedManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_or_create_estimate(self):
        """The project's primary Estimate. New projects get one via the setup
        wizard, but this self-heals for any project that predates that (or
        was created outside the wizard, e.g. via admin)."""
        return self.estimates.order_by('created_at').first() or Estimate.objects.create(project=self)


class JobSettings(models.Model):
    """Answers captured by the Job Settings Wizard when a Project is created.
    Parameterizes every Tool calculation for that Project."""

    class StudSpacing(models.IntegerChoices):
        SIXTEEN_OC = 16, '16" OC'
        TWENTY_FOUR_OC = 24, '24" OC'

    class RoofFraming(models.TextChoices):
        RAFTERS = 'rafters', 'Rafters'
        TRUSSES = 'trusses', 'Trusses'
        BOTH = 'both', 'Both'

    class FoundationType(models.TextChoices):
        SLAB = 'slab', 'Slab on grade'
        CRAWL_SPACE = 'crawl_space', 'Crawl space'
        FULL_BASEMENT = 'full_basement', 'Full basement'

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='job_settings')
    num_floors = models.PositiveSmallIntegerField(default=1)
    foundation_type = models.CharField(
        max_length=20, choices=FoundationType.choices, default=FoundationType.SLAB,
        help_text='A slab has no floor framing; a crawl space or full basement does.',
    )
    basement_wall_height_in = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    first_floor_wall_height_in = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal('109.125'))
    second_floor_wall_height_in = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    stud_spacing_in = models.PositiveSmallIntegerField(
        choices=StudSpacing.choices, default=StudSpacing.SIXTEEN_OC,
    )
    roof_framing = models.CharField(max_length=20, choices=RoofFraming.choices, default=RoofFraming.TRUSSES)
    roof_pitch_rise_per_12 = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Rise in inches per 12" of run, e.g. 6 for a 6/12 pitch. Leave blank if not yet known.',
    )
    floor_material = models.CharField(max_length=255, blank=True)
    siding_material = models.CharField(
        max_length=255, blank=True,
        help_text='E.g. "Vinyl siding", "Hardie board", "Brick veneer".',
    )

    def __str__(self):
        return f'Job settings for {self.project.name}'


class ProjectTemplateQuerySet(models.QuerySet):
    def visible_to(self, account):
        return self.filter(models.Q(account=account) | models.Q(account__isnull=True))


class ProjectTemplate(models.Model):
    """Reusable job-setting presets shown in the New Project flow."""

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='project_templates',
        null=True, blank=True,
    )
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    is_favorite = models.BooleanField(
        default=False,
        help_text='Shown first in the New Project flow and template library for this account.',
    )
    sort_order = models.PositiveSmallIntegerField(default=100)
    num_floors = models.PositiveSmallIntegerField(default=1)
    foundation_type = models.CharField(
        max_length=20, choices=JobSettings.FoundationType.choices, default=JobSettings.FoundationType.SLAB,
    )
    basement_wall_height_in = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    first_floor_wall_height_in = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal('109.125'))
    second_floor_wall_height_in = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    stud_spacing_in = models.PositiveSmallIntegerField(
        choices=JobSettings.StudSpacing.choices, default=JobSettings.StudSpacing.SIXTEEN_OC,
    )
    roof_framing = models.CharField(
        max_length=20, choices=JobSettings.RoofFraming.choices, default=JobSettings.RoofFraming.TRUSSES,
    )
    roof_pitch_rise_per_12 = models.PositiveSmallIntegerField(null=True, blank=True)
    floor_material = models.CharField(max_length=255, blank=True)
    siding_material = models.CharField(max_length=255, blank=True)

    objects = ProjectTemplateQuerySet.as_manager()

    class Meta:
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['account', 'name'], name='unique_project_template_name_per_account'),
        ]

    def __str__(self):
        return self.name

    @property
    def is_system(self):
        return self.account_id is None

    def to_form_initial(self):
        return {
            'template': self.pk,
            'num_floors': self.num_floors,
            'foundation_type': self.foundation_type,
            'basement_wall_height_in': self.basement_wall_height_in,
            'first_floor_wall_height_in': self.first_floor_wall_height_in,
            'second_floor_wall_height_in': self.second_floor_wall_height_in,
            'stud_spacing_in': self.stud_spacing_in,
            'roof_framing': self.roof_framing,
            'roof_pitch_rise_per_12': self.roof_pitch_rise_per_12,
            'floor_material': self.floor_material,
            'siding_material': self.siding_material,
        }

    def duplicate_for_account(self, account):
        suffix = ' (Copy)'
        base_name = f'{self.name}{suffix}'
        name = base_name
        counter = 2
        while ProjectTemplate.objects.filter(account=account, name=name).exists():
            name = f'{base_name} {counter}'
            counter += 1
        return ProjectTemplate.objects.create(
            account=account,
            name=name,
            description=self.description,
            is_favorite=False,
            sort_order=self.sort_order,
            num_floors=self.num_floors,
            foundation_type=self.foundation_type,
            basement_wall_height_in=self.basement_wall_height_in,
            first_floor_wall_height_in=self.first_floor_wall_height_in,
            second_floor_wall_height_in=self.second_floor_wall_height_in,
            stud_spacing_in=self.stud_spacing_in,
            roof_framing=self.roof_framing,
            roof_pitch_rise_per_12=self.roof_pitch_rise_per_12,
            floor_material=self.floor_material,
            siding_material=self.siding_material,
        )

    @classmethod
    def from_job_settings(cls, job_settings, **overrides):
        return cls(
            num_floors=job_settings.num_floors,
            foundation_type=job_settings.foundation_type,
            basement_wall_height_in=job_settings.basement_wall_height_in,
            first_floor_wall_height_in=job_settings.first_floor_wall_height_in,
            second_floor_wall_height_in=job_settings.second_floor_wall_height_in,
            stud_spacing_in=job_settings.stud_spacing_in,
            roof_framing=job_settings.roof_framing,
            roof_pitch_rise_per_12=job_settings.roof_pitch_rise_per_12,
            floor_material=job_settings.floor_material,
            siding_material=job_settings.siding_material,
            **overrides,
        )


class EstimateQuerySet(models.QuerySet):
    def for_account(self, account):
        return self.filter(project__account=account)


class Estimate(models.Model):
    """A versioned snapshot of materials for a Project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='estimates')
    name = models.CharField(max_length=255, default='Estimate 1')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = EstimateQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project.name} - {self.name}'

    def get_absolute_url(self):
        return reverse('estimating:estimate-detail', args=[self.pk])
