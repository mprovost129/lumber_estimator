from django import forms
from django.core.validators import FileExtensionValidator

from .models import Plan


class PlanUploadForm(forms.ModelForm):
    original_file = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=['pdf'])])

    class Meta:
        model = Plan
        fields = ['original_file']
