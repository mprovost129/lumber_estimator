from decimal import Decimal, InvalidOperation

from django import forms
from django.forms import inlineformset_factory
from django.utils.text import slugify

from catalog.forms import MaterialProductInputMixin
from catalog.models import MaterialLength, MaterialProduct

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


class MaterialForm(MaterialProductInputMixin, BootstrapFormMixin, forms.ModelForm):
    supported_input_types = forms.MultipleChoiceField(
        choices=MaterialProduct.InputType.choices,
        widget=forms.CheckboxSelectMultiple,
    )
    lengths = forms.CharField(
        required=False,
        help_text='For feet materials, enter stock lengths in feet, separated by commas or semicolons.',
    )
    default_length = forms.DecimalField(
        required=False, decimal_places=5, max_digits=8,
        help_text='Default stock length used for run-length calculations.',
    )
    unit_cost = forms.DecimalField(
        required=False, decimal_places=2, max_digits=10, min_value=0,
        label='Unit cost (optional)',
        help_text='Your cost per ordering unit (per stock piece, per box, or per each). '
                  'Leave blank to keep this material unpriced.',
    )

    class Meta:
        model = MaterialProduct
        fields = [
            'name', 'category', 'species', 'grade', 'nominal_dimension',
            'supported_input_types', 'input_type', 'quantity_per_box',
        ]
        labels = {'nominal_dimension': 'Dimension'}

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        if self.instance.pk and self.instance.input_type == MaterialProduct.InputType.FT:
            lengths = list(self.instance.lengths.order_by('length_ft').values_list('length_ft', flat=True))
            self.fields['lengths'].initial = ', '.join(self._format_length(length) for length in lengths)
            default = self.instance.lengths.filter(is_default=True).first()
            if default is not None:
                self.fields['default_length'].initial = default.length_ft
        if self.instance.pk and account is not None:
            existing_price = self.instance.prices.filter(account=account).first()
            if existing_price is not None:
                self.fields['unit_cost'].initial = existing_price.unit_cost

    def clean_lengths(self):
        raw = str(self.cleaned_data.get('lengths') or '').replace(';', ',')
        parsed = []
        for part in raw.split(','):
            value = part.strip()
            if not value:
                continue
            try:
                parsed.append(Decimal(value))
            except (InvalidOperation, ValueError):
                raise forms.ValidationError('Lengths must be numbers of feet.') from None
        return parsed

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            return name
        slug = slugify(name)
        query = MaterialProduct.objects.filter(account=self.account, slug=slug)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise forms.ValidationError('A material with that name already exists in your library.')
        return name

    def clean(self):
        cleaned = super().clean()
        input_type = cleaned.get('input_type')
        supported_input_types = cleaned.get('supported_input_types') or []
        lengths = cleaned.get('lengths') or []
        default_length = cleaned.get('default_length')

        if MaterialProduct.InputType.FT in supported_input_types:
            if not lengths:
                self.add_error('lengths', 'Feet materials need at least one stock length.')
            elif default_length is None:
                cleaned['default_length'] = lengths[0]
            elif default_length not in lengths:
                self.add_error('default_length', 'Default length must be one of the listed stock lengths.')
        else:
            cleaned['lengths'] = []
            cleaned['default_length'] = None

        if MaterialProduct.InputType.BOX not in supported_input_types:
            cleaned['quantity_per_box'] = None
            self.cleaned_data['quantity_per_box'] = None

        product = self.instance if self.instance.pk else MaterialProduct(account=self.account)
        for field in self.Meta.fields:
            setattr(product, field, cleaned.get(field))
        try:
            product.clean()
        except forms.ValidationError as exc:
            self.add_error(None, exc)
        return cleaned

    def save(self, commit=True):
        product = super().save(commit=False)
        if product.account_id is None and self.account is not None:
            product.account = self.account
        product.supported_input_types = self.cleaned_data['supported_input_types']
        if not product.slug:
            product.slug = slugify(product.name)
        if not commit:
            return product

        product.full_clean(exclude=['account'])
        product.save()
        product.lengths.all().delete()
        if product.supports_input_type(MaterialProduct.InputType.FT):
            default_length = self.cleaned_data['default_length']
            for length in self.cleaned_data['lengths']:
                MaterialLength.objects.create(
                    product=product, length_ft=length, is_default=(length == default_length),
                )
        self._save_price(product)
        return product

    def _save_price(self, product):
        """Upsert the account's private unit cost for this material. Account is
        required to price; a blank cost clears any existing price so a material
        can be un-priced again. Never creates a global price row."""
        from catalog.models import MaterialPrice

        if self.account is None:
            return
        unit_cost = self.cleaned_data.get('unit_cost')
        if unit_cost is None:
            MaterialPrice.objects.filter(account=self.account, material=product).delete()
        else:
            MaterialPrice.objects.update_or_create(
                account=self.account, material=product,
                defaults={'unit_cost': unit_cost},
            )

    @staticmethod
    def _format_length(value):
        return format(Decimal(str(value)).normalize(), 'f')


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
