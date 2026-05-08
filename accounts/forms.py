from django.contrib.auth.forms import UserCreationForm
from .models import *
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .models import CustomUser
import re


class CreateUserForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = (
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )
        widgets = {
            "first_name": forms.TextInput(attrs={
                "class": "form-field pl-10"
            }),
            "last_name": forms.TextInput(attrs={
                "class": "form-field pl-10"
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-field pl-10"
            }),
        }

    def __init__(self, *args, **kwargs):
        # Accept role, and organization as kwargs
        self.role = kwargs.pop('role', None)
        self.organization_id = kwargs.pop('organization_id', None)

        super().__init__(*args, **kwargs)

        # Pre-fill the fields with the passed-in data
        if self.role:
            self.fields['role'] = self.role  # Assuming you want to add a field for role
        if self.organization_id:
            self.fields['organization_id'] = self.organization_id  # Same for organization ID if you need it

        # Manually style password fields (Django ignores Meta.widgets for these)
        self.fields["password1"].widget.attrs.update({
            "class": "form-field pl-10",
            "placeholder": _("Password"),
        })
        self.fields["password2"].widget.attrs.update({
            "class": "form-field pl-10",
            "placeholder": _("Confirm password"),
        })

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and CustomUser.objects.filter(email=email).exists():
            raise ValidationError(_("This email is already registered."))
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if not password1 or not password2:
            raise ValidationError(_("Password fields cannot be empty."))

        if password1 != password2:
            raise ValidationError(_("The two password fields must match."))

        # Password strength checks
        if len(password1) < 8:
            raise ValidationError(_("Password must be at least 8 characters long."))
        if not re.search(r"[A-Z]", password1):
            raise ValidationError(_("Password must contain at least one uppercase letter."))
        if not re.search(r"[a-z]", password1):
            raise ValidationError(_("Password must contain at least one lowercase letter."))
        if not re.search(r"\d", password1):
            raise ValidationError(_("Password must contain at least one digit."))
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password1):
            raise ValidationError(_("Password must contain at least one special character."))

        return password2

    def save(self, commit=True):
        user = super().save(commit=False)

        if user.email:
            user.username = user.email.split('@')[0]

        if commit:
            user.save()

        return user


class EditUserForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(EditUserForm, self).__init__(*args, **kwargs)

        # Check if the user has the 'manage_roles' permission
        if user and not user.has_perm('accounts.manage_roles'):
            self.fields.pop('role')

    class Meta:
        model = CustomUser
        fields = (
            'first_name',
            'last_name',
            'username',
            'email',
            'phone_number',
        )
        widgets = {
            'first_name': forms.TextInput(attrs={'class': "required form-field pl-10"}),
            'last_name': forms.TextInput(attrs={'class': "required form-field pl-10"}),
            'username': forms.TextInput(attrs={'class': "form-field pl-10"}),
            'email': forms.TextInput(attrs={'class': "required form-field pl-10"}),
            'phone_number': forms.TextInput(attrs={'class': "form-field pl-10"}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = (
            'gender',
            'image',
        )
        widgets = {
            'gender': forms.Select(attrs={'class': "required mb-1 px-3 py-2 rounded-md border focus:border-none  focus:outline-none focus:ring-4 focus:ring-sky-600 w-full"}),
        }


class RolePermissionForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ("permissions",)

    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        required=False
    )