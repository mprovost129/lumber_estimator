from django.contrib import admin

from .models import Estimate, JobSettings, Project, ProjectTemplate


class JobSettingsInline(admin.StackedInline):
    model = JobSettings
    extra = 0


class EstimateInline(admin.TabularInline):
    model = Estimate
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'client', 'status', 'created_at')
    list_filter = ('status', 'account')
    search_fields = ('name', 'client')
    inlines = [JobSettingsInline, EstimateInline]


@admin.register(ProjectTemplate)
class ProjectTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'num_floors', 'foundation_type', 'first_floor_wall_height_in')
    list_filter = ('account', 'foundation_type', 'num_floors')
    search_fields = ('name', 'description')
