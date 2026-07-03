from django.db import models

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

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='job_settings')
    num_floors = models.PositiveSmallIntegerField(default=1)
    has_basement = models.BooleanField(default=False)
    basement_wall_height_in = models.PositiveSmallIntegerField(null=True, blank=True)
    first_floor_wall_height_in = models.PositiveSmallIntegerField(default=108)  # 9'
    second_floor_wall_height_in = models.PositiveSmallIntegerField(null=True, blank=True)
    stud_spacing_in = models.PositiveSmallIntegerField(
        choices=StudSpacing.choices, default=StudSpacing.SIXTEEN_OC,
    )
    roof_framing = models.CharField(max_length=20, choices=RoofFraming.choices, default=RoofFraming.TRUSSES)
    floor_material = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f'Job settings for {self.project.name}'


class Estimate(models.Model):
    """A versioned snapshot of materials for a Project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='estimates')
    name = models.CharField(max_length=255, default='Estimate 1')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project.name} - {self.name}'
