"""
Custom allauth signup form.

IMPORTANT: ACCOUNT_SIGNUP_FORM_CLASS must be a plain Django Form
(NOT a subclass of allauth's SignupForm) to avoid a circular import.
Allauth merges this form's extra fields into the base signup form automatically.
The signup() method is called by allauth after the user is saved.
"""
from django import forms


class CustomSignupForm(forms.Form):
    """Extra field(s) appended to the allauth signup form."""

    company_name = forms.CharField(
        max_length=255,
        required=True,
        label='Company Name',
        widget=forms.TextInput(attrs={
            'placeholder': 'Your Company or Organization Name',
            'autocomplete': 'organization',
        }),
    )

    def signup(self, request, user):
        """
        Called by allauth after the user is created.
        Org creation is handled in CustomAccountAdapter.save_user(),
        which reads form.cleaned_data['company_name'].
        Nothing extra needed here.
        """
        pass
