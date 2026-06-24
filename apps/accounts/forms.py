from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.contrib.auth.models import User
from .models import UserProfile, SignupRequest

class SignupRequestForm(forms.ModelForm):
    class Meta:
        model = SignupRequest
        fields = ['first_name', 'last_name', 'email', 'mobile_number', 'organization_name']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email Address'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Mobile Number'}),
            'organization_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Organization Name'}),
        }

class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'readonly': 'readonly'}))
    
    class Meta:
        model = UserProfile
        fields = [
            'mobile_number',
            'country',
            'gender',
            'org_name',
            'org_id'
        ]
        widgets = {
            'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'org_name': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'org_id': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance', None)
        if instance:
            # If we have a UserProfile instance, initialize with User data
            initial = kwargs.get('initial', {})
            initial['first_name'] = instance.user.first_name
            initial['last_name'] = instance.user.last_name
            initial['username'] = instance.user.username
            initial['email'] = instance.user.email
            kwargs['initial'] = initial
        
        super().__init__(*args, **kwargs)
        
        # Make specific fields optional
        optional_fields = [
            'org_name', 
            'org_id'
        ]
        for field_name in optional_fields:
            self.fields[field_name].required = False
            
        # Prevent these fields from being modified via POST
        if 'username' in self.fields:
            self.fields['username'].disabled = True
        if 'org_name' in self.fields:
            self.fields['org_name'].disabled = True
        if 'org_id' in self.fields:
            self.fields['org_id'].disabled = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError("Email is required.")
        
        # Get the current user
        current_user = self.instance.user if self.instance else None
        
        if email and current_user and email != current_user.email:
            if User.objects.filter(email=email).exclude(id=current_user.id).exists():
                raise forms.ValidationError("This email is already in use.")
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError("Username is required.")
        
        # Get the current user
        current_user = self.instance.user if self.instance else None
        
        if username and current_user and username != current_user.username:
            if User.objects.filter(username=username).exclude(id=current_user.id).exists():
                raise forms.ValidationError("This username is already in use.")
        return username
    
    def clean_mobile_number(self):
        mobile_number = self.cleaned_data.get('mobile_number')
        if mobile_number:
            # Remove any non-digit characters
            mobile_number = ''.join(filter(str.isdigit, mobile_number))
            
            # Validate mobile number length (adjust as needed)
            if len(mobile_number) < 10:
                raise forms.ValidationError("Invalid mobile number. Please enter a valid number.")
            
            # Check for duplicate mobile number
            if mobile_number and self.instance and mobile_number != self.instance.mobile_number:
                if UserProfile.objects.filter(mobile_number=mobile_number).exclude(id=self.instance.id).exists():
                    raise forms.ValidationError("This mobile number is already in use.")
        
        return mobile_number
    
    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def add_warning(self, message):
        """
        Add a warning message to the form.
        This method can be used to add non-blocking warnings.
        """
        if not hasattr(self, '_warnings'):
            self._warnings = []
        self._warnings.append(message)

    def get_warnings(self):
        """
        Retrieve warning messages.
        """
        return getattr(self, '_warnings', [])
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Update the associated User model
        user = profile.user
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.username = self.cleaned_data.get('username')
        user.email = self.cleaned_data.get('email')
        
        # Check if email has changed
        if self.cleaned_data.get('email') != user.email:
            profile.email_verified = False
        
        # Check if mobile number has changed
        mobile_number = self.cleaned_data.get('mobile_number')
        if mobile_number and mobile_number != self.initial.get('mobile_number'):
            profile.mobile_number_verified = False
            profile.mobile_number = mobile_number
        
        if commit:
            user.save()
            profile.save()
        
        return profile

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'confirm_password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")

        return cleaned_data
        
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        
        if commit:
            user.save()
            # Create an associated profile
            UserProfile.objects.create(user=user)
            
        return user