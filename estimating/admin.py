from django.contrib import admin

from .models import Assembly, CalculationRule, Formula, LineItem, LoadType


class CalculationRuleInline(admin.TabularInline):
    model = CalculationRule
    extra = 1


@admin.register(Assembly)
class AssemblyAdmin(admin.ModelAdmin):
    list_display = ('name', 'tool_type', 'category', 'account')
    list_filter = ('category', 'tool_type', 'account')
    search_fields = ('name',)
    inlines = [CalculationRuleInline]


@admin.register(Formula)
class FormulaAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_kind', 'account', 'base_formula', 'multiplier', 'addend')
    list_filter = ('measurement_kind', 'account')
    search_fields = ('name', 'description')


@admin.register(LineItem)
class LineItemAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'estimate', 'load_type', 'category', 'source', 'quantity', 'material', 'created_at')
    list_filter = ('load_type', 'category', 'source', 'material')


@admin.register(LoadType)
class LoadTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'account')
    list_filter = ('account',)
    search_fields = ('name',)
