from django.contrib import admin

from .models import Plan, PlanPage, ToolPreset, Trace


class PlanPageInline(admin.TabularInline):
    model = PlanPage
    extra = 0
    fields = ('page_number', 'label', 'image', 'thumbnail')


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'uploaded_at')
    list_filter = ('project',)
    inlines = [PlanPageInline]


@admin.register(PlanPage)
class PlanPageAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'plan', 'page_number', 'label')
    list_filter = ('plan',)


@admin.register(Trace)
class TraceAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'tool_type', 'material', 'load_type', 'created_at')
    list_filter = ('tool_type', 'material', 'load_type')


@admin.register(ToolPreset)
class ToolPresetAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'tool_type', 'material', 'load_type', 'assembly', 'is_favorite')
    list_filter = ('tool_type', 'account', 'is_favorite')
