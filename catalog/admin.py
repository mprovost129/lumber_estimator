from django.contrib import admin

from .models import MaterialLength, MaterialProduct


class MaterialLengthInline(admin.TabularInline):
    model = MaterialLength
    extra = 1


@admin.register(MaterialProduct)
class MaterialProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'input_type', 'species', 'grade', 'nominal_dimension')
    list_filter = ('input_type', 'account', 'species', 'grade')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [MaterialLengthInline]

    class Media:
        js = ('catalog/admin/material_product.js',)
