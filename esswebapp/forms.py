from django import forms


class LoginForm(forms.Form):
    """Login form accepting email OR mobile number + password"""
    login_id = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'you@ekseshreshtha.org or mobile number',
            'autocomplete': 'username',
            'required': True,
        }),
        label='Email or mobile number'
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