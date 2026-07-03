from django.contrib import admin

from .models import Estimate, JobSettings, Project


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
