from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

User = get_user_model()


class SignUpForm(forms.Form):
    """Public self-serve registration: a company name becomes the Account
    (the tenant), and the email/password become its first user."""

    company_name = forms.CharField(
        max_length=255, label='Company name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Acme Framing LLC', 'autofocus': True}),
    )
    email = forms.EmailField(
        label='Work email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@company.com'}),
    )
    password1 = forms.CharField(
        label='Password', strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label='Confirm password', strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError('An account with this email already exists. Try logging in instead.')
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('The two password fields did not match.')
        password_validation.validate_password(password2)
        return password2

    def save(self):
        from .models import Account

        account = Account.objects.create(name=self.cleaned_data['company_name'].strip())
        return User.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1'],
            account=account,
        )


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['keep_tool_active_after_draw']
        labels = {
            'keep_tool_active_after_draw': 'Keep the current drawing tool active after finishing a trace',
        }
        widgets = {
            'keep_tool_active_after_draw': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
