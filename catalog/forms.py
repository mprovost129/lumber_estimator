from django import forms

from .models import MaterialProduct


class MaterialProductInputMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supported_input_types'].choices = MaterialProduct.InputType.choices
        self.fields['supported_input_types'].widget = forms.CheckboxSelectMultiple()
        self.fields['supported_input_types'].help_text = (
            'Choose every ordering method this material should support.'
        )
        supported = []
        if getattr(self.instance, 'pk', None):
            supported = self.instance.normalized_supported_input_types()
        elif self.initial.get('supported_input_types'):
            supported = self.initial['supported_input_types']
        elif self.initial.get('input_type'):
            supported = [self.initial['input_type']]
        else:
            supported = [MaterialProduct.InputType.EACH]
        self.fields['supported_input_types'].initial = supported

    def clean_supported_input_types(self):
        supported = self.cleaned_data.get('supported_input_types') or []
        if not supported:
            raise forms.ValidationError('Choose at least one supported input type.')
        return supported

    def clean(self):
        cleaned = super().clean()
        supported = cleaned.get('supported_input_types') or []
        default_input_type = cleaned.get('input_type')
        if default_input_type and default_input_type not in supported:
            self.add_error('input_type', 'Default input type must also be checked in supported input types.')
        return cleaned
