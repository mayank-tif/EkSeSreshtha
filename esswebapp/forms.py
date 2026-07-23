from django import forms


class LoginForm(forms.Form):
    """Login form with email and password fields"""
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'you@ekseshreshtha.org',
            'autocomplete': 'email',
            'required': True,
        }),
        label='Email address'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
            'required': True,
        }),
        label='Password'
    )
    remember = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'id': 'login-remember',
        }),
        label='Keep me signed in'
    )