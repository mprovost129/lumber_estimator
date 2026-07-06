from decimal import Decimal

from django import forms

from .models import JobSettings, Project, ProjectTemplate


class BootstrapFormMixin:
    """Applies Bootstrap classes to every widget so templates can render
    fields directly."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select')
            else:
                widget.attrs.setdefault('class', 'form-control')


class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'client']


HEIGHT_HELP_TEXT = 'Examples: 97.125 = 8 ft 1-1/8 in, 109.125 = 9 ft 1-1/8 in.'


class JobSettingsForm(BootstrapFormMixin, forms.ModelForm):
    """The Job Settings questions. Used inside the setup wizard and on its own
    for editing settings after a project exists."""

    class Meta:
        model = JobSettings
        fields = [
            'num_floors', 'foundation_type', 'basement_wall_height_in',
            'first_floor_wall_height_in', 'second_floor_wall_height_in',
            'stud_spacing_in', 'roof_framing', 'roof_pitch_rise_per_12',
            'floor_material', 'siding_material',
        ]
        labels = {
            'num_floors': 'Number of floors',
            'foundation_type': 'Foundation',
            'basement_wall_height_in': 'Basement wall height (inches)',
            'first_floor_wall_height_in': '1st floor wall height (inches)',
            'second_floor_wall_height_in': '2nd floor wall height (inches)',
            'stud_spacing_in': 'Stud spacing',
            'roof_framing': 'Roof framing',
            'roof_pitch_rise_per_12': 'Roof pitch (rise per 12" run)',
            'floor_material': 'Floor system / material',
            'siding_material': 'Siding / exterior finish',
        }
        help_texts = {
            'first_floor_wall_height_in': HEIGHT_HELP_TEXT,
            'basement_wall_height_in': HEIGHT_HELP_TEXT,
            'second_floor_wall_height_in': HEIGHT_HELP_TEXT,
            'roof_pitch_rise_per_12': 'E.g. 6 for a 6/12 pitch. Leave blank if not yet known.',
            'floor_material': 'E.g. "2x10 joists + 3/4 T&G plywood" or "I-joists".',
            'siding_material': 'E.g. "Vinyl siding", "Hardie board", "Brick veneer".',
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('foundation_type') == JobSettings.FoundationType.FULL_BASEMENT \
                and not cleaned.get('basement_wall_height_in'):
            self.add_error('basement_wall_height_in', 'Required for a full basement foundation.')
        if (cleaned.get('num_floors') or 1) >= 2 and not cleaned.get('second_floor_wall_height_in'):
            self.add_error('second_floor_wall_height_in', 'Required for projects with 2+ floors.')
        return cleaned


class ProjectSetupForm(ProjectForm):
    """The Project Setup Wizard: project info + every JobSettings question in
    one submission, rendered as steps client-side. Saving creates the Project,
    its JobSettings, and its first Estimate."""

    class Meta:
        model = Project
        fields = ProjectForm.Meta.fields

    template = forms.ModelChoiceField(
        queryset=ProjectTemplate.objects.none(), required=False, widget=forms.HiddenInput(),
    )

    # Pull the JobSettings fields in explicitly since two ModelForm parents
    # can't merge Meta definitions.
    num_floors = forms.IntegerField(min_value=1, max_value=4, initial=1, label='Number of floors')
    foundation_type = forms.ChoiceField(
        choices=JobSettings.FoundationType.choices,
        initial=JobSettings.FoundationType.SLAB, label='Foundation',
        help_text='A slab has no floor framing; a crawl space or full basement does.',
    )
    basement_wall_height_in = forms.DecimalField(
        required=False, min_value=Decimal('48'), decimal_places=3, max_digits=6,
        label='Basement wall height (inches)', help_text=HEIGHT_HELP_TEXT,
    )
    first_floor_wall_height_in = forms.DecimalField(
        min_value=Decimal('72'), decimal_places=3, max_digits=6, initial=Decimal('109.125'),
        label='1st floor wall height (inches)', help_text=HEIGHT_HELP_TEXT,
    )
    second_floor_wall_height_in = forms.DecimalField(
        required=False, min_value=Decimal('72'), decimal_places=3, max_digits=6,
        label='2nd floor wall height (inches)', help_text=HEIGHT_HELP_TEXT,
    )
    stud_spacing_in = forms.TypedChoiceField(
        choices=JobSettings.StudSpacing.choices, coerce=int,
        initial=JobSettings.StudSpacing.SIXTEEN_OC, label='Stud spacing',
    )
    roof_framing = forms.ChoiceField(
        choices=JobSettings.RoofFraming.choices,
        initial=JobSettings.RoofFraming.TRUSSES, label='Roof framing',
    )
    roof_pitch_rise_per_12 = forms.IntegerField(
        required=False, min_value=1, max_value=24, label='Roof pitch (rise per 12" run)',
        help_text='E.g. 6 for a 6/12 pitch. Leave blank if not yet known.',
    )
    floor_material = forms.CharField(
        required=False, label='Floor system / material',
        help_text='E.g. "2x10 joists + 3/4 T&G plywood" or "I-joists".',
    )
    siding_material = forms.CharField(
        required=False, label='Siding / exterior finish',
        help_text='E.g. "Vinyl siding", "Hardie board", "Brick veneer".',
    )

    def __init__(self, *args, account=None, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        self.fields['template'].queryset = ProjectTemplate.objects.visible_to(account) if account else ProjectTemplate.objects.none()
        if template is not None and not self.is_bound:
            for field_name, value in template.to_form_initial().items():
                self.fields[field_name].initial = value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('foundation_type') == JobSettings.FoundationType.FULL_BASEMENT \
                and not cleaned.get('basement_wall_height_in'):
            self.add_error('basement_wall_height_in', 'Required for a full basement foundation.')
        if (cleaned.get('num_floors') or 1) >= 2 and not cleaned.get('second_floor_wall_height_in'):
            self.add_error('second_floor_wall_height_in', 'Required for projects with 2+ floors.')
        return cleaned

    def save_with_settings(self, account):
        """Create the Project plus its JobSettings and first Estimate."""
        from .models import Estimate

        project = Project.objects.create(
            account=account,
            name=self.cleaned_data['name'],
            client=self.cleaned_data.get('client', ''),
        )
        JobSettings.objects.create(
            project=project,
            num_floors=self.cleaned_data['num_floors'],
            foundation_type=self.cleaned_data['foundation_type'],
            basement_wall_height_in=self.cleaned_data.get('basement_wall_height_in'),
            first_floor_wall_height_in=self.cleaned_data['first_floor_wall_height_in'],
            second_floor_wall_height_in=self.cleaned_data.get('second_floor_wall_height_in'),
            stud_spacing_in=self.cleaned_data['stud_spacing_in'],
            roof_framing=self.cleaned_data['roof_framing'],
            roof_pitch_rise_per_12=self.cleaned_data.get('roof_pitch_rise_per_12'),
            floor_material=self.cleaned_data.get('floor_material', ''),
            siding_material=self.cleaned_data.get('siding_material', ''),
        )
        Estimate.objects.create(project=project)
        return project


class ProjectTemplateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProjectTemplate
        fields = [
            'name', 'description', 'num_floors', 'foundation_type', 'basement_wall_height_in',
            'first_floor_wall_height_in', 'second_floor_wall_height_in', 'stud_spacing_in',
            'roof_framing', 'roof_pitch_rise_per_12', 'floor_material', 'siding_material',
        ]
        help_texts = {
            'description': 'Short label shown on the New Project screen.',
            'basement_wall_height_in': HEIGHT_HELP_TEXT,
            'first_floor_wall_height_in': HEIGHT_HELP_TEXT,
            'second_floor_wall_height_in': HEIGHT_HELP_TEXT,
            'roof_pitch_rise_per_12': 'E.g. 6 for a 6/12 pitch. Leave blank if not yet known.',
            'floor_material': 'E.g. "2x10 joists + 3/4 T&G plywood" or "I-joists".',
            'siding_material': 'E.g. "Vinyl siding", "Hardie board", "Brick veneer".',
        }
        labels = {
            'num_floors': 'Number of floors',
            'foundation_type': 'Foundation',
            'basement_wall_height_in': 'Basement wall height (inches)',
            'first_floor_wall_height_in': '1st floor wall height (inches)',
            'second_floor_wall_height_in': '2nd floor wall height (inches)',
            'stud_spacing_in': 'Stud spacing',
            'roof_framing': 'Roof framing',
            'roof_pitch_rise_per_12': 'Roof pitch (rise per 12" run)',
            'floor_material': 'Floor system / material',
            'siding_material': 'Siding / exterior finish',
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('foundation_type') == JobSettings.FoundationType.FULL_BASEMENT \
                and not cleaned.get('basement_wall_height_in'):
            self.add_error('basement_wall_height_in', 'Required for a full basement foundation.')
        if (cleaned.get('num_floors') or 1) >= 2 and not cleaned.get('second_floor_wall_height_in'):
            self.add_error('second_floor_wall_height_in', 'Required for projects with 2+ floors.')
        return cleaned
