from django import forms
from django.contrib import admin

from .forms import MaterialProductInputMixin
from .models import MaterialLength, MaterialProduct


class MaterialLengthInline(admin.TabularInline):
    model = MaterialLength
    extra = 1


class AdminMaterialProductForm(MaterialProductInputMixin, forms.ModelForm):
    supported_input_types = forms.MultipleChoiceField(
        choices=MaterialProduct.InputType.choices,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = MaterialProduct
        fields = '__all__'


@admin.register(MaterialProduct)
class MaterialProductAdmin(admin.ModelAdmin):
    form = AdminMaterialProductForm
    list_display = (
        'name', 'account', 'input_type', 'supported_input_types_summary', 'species', 'grade', 'nominal_dimension',
    )
    list_filter = ('input_type', 'account', 'species', 'grade')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [MaterialLengthInline]

    @admin.display(description='Supported inputs')
    def supported_input_types_summary(self, obj):
        return ', '.join(obj.supported_input_type_labels)

    class Media:
        js = ('catalog/admin/material_product.js',)
