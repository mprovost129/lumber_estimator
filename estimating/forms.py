from django import forms
from django.forms import inlineformset_factory

from catalog.models import MaterialProduct

from .models import Assembly, CalculationRule, Formula, LineItem


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')


class ManualLineItemForm(forms.ModelForm):
    """Add a material line directly to an Estimate, independent of any trace."""

    class Meta:
        model = LineItem
        fields = ['material', 'role', 'category', 'quantity', 'length_ft']
        labels = {'role': 'Label', 'category': 'System', 'length_ft': 'Length (ft, optional)'}

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        if account is not None:
            self.fields['material'].queryset = MaterialProduct.objects.visible_to(account)
        self.fields['material'].widget.attrs['class'] = 'form-select'
        self.fields['category'].widget.attrs['class'] = 'form-select'
        for name in ('role', 'quantity', 'length_ft'):
            self.fields[name].widget.attrs['class'] = 'form-control'
        self.fields['role'].required = False
        self.fields['length_ft'].required = False
        self.fields['category'].required = False

    def clean_category(self):
        # A plain CharField+choices (not a ForeignKey) gets no automatic blank
        # option, so an omitted/blank submission lands here as '' rather than
        # the model's MISC default - normalize it explicitly.
        return self.cleaned_data.get('category') or Assembly.Category.MISC


class FormulaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Formula
        fields = ['name', 'measurement_kind', 'base_formula', 'multiplier', 'addend', 'description']
        help_texts = {
            'multiplier': 'Example: use 3 to turn Line LF into Line LF × 3.',
            'addend': 'Optional fixed amount added after multiplication.',
        }

    def __init__(self, *args, account, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        self.fields['base_formula'].queryset = Formula.objects.visible_to(account)

    def save(self, commit=True):
        formula = super().save(commit=False)
        formula.account = self.account
        if commit:
            formula.full_clean()
            formula.save()
        return formula


class AssemblyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Assembly
        fields = ['name', 'tool_type', 'category', 'wall_subtype', 'opening_kind', 'beam_type', 'description']
        labels = {'category': 'System'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False

    def clean_category(self):
        # See ManualLineItemForm.clean_category - same plain CharField+choices
        # gotcha (no automatic blank option), same MISC-default normalization.
        return self.cleaned_data.get('category') or Assembly.Category.MISC


class CalculationRuleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CalculationRule
        fields = [
            'role', 'material', 'formula', 'formula_kind', 'multiplier',
            'extra', 'coverage_sqft', 'units_per_measurement', 'waste_factor', 'order',
            'corner_stud_count', 't_intersection_stud_count', 't_backer_stud_count',
        ]

    def __init__(self, *args, account, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = MaterialProduct.objects.visible_to(account)
        self.fields['formula'].queryset = Formula.objects.visible_to(account)
        self.fields['formula'].required = False
        self.fields['formula_kind'].required = False


CalculationRuleFormSet = inlineformset_factory(
    Assembly,
    CalculationRule,
    form=CalculationRuleForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)
