from django.shortcuts import render, redirect
from django.views import View
from django.utils import timezone

from APIS.models import User, Role
from APIS.utils import hash_password
from .forms import LoginForm


# Allowed role codes for web login
ALLOWED_WEB_ROLES = ['SUPER_ADMIN', 'REGIONAL_ADMIN']


def get_user_session_data(user):
    """Extract user data for session storage"""
    role_code = user.role.role_code if user.role else None
    
    session_data = {
        'user_id': user.id,
        'email': user.email,
        'name': user.name,
        'phone_number': user.phone_number,
        'role_id': user.role_id,
        'role_code': role_code,
        'role_name': user.role.role_name if user.role else None,
        'is_super_admin': role_code == 'SUPER_ADMIN',
        'is_regional_admin': role_code == 'REGIONAL_ADMIN',
        'last_login': str(timezone.now()),
    }
    
    # Add regional admin specific data
    if role_code == 'REGIONAL_ADMIN' and hasattr(user, 'regional_admin'):
        ra = user.regional_admin
        session_data.update({
            'district_id': ra.district_id,
            'vidhan_sabha_id': ra.vidhan_sabha_id,
            'panchayat_id': ra.panchayat_id,
            'village_id': ra.village_id,
        })
    
    # Add super admin specific data
    if role_code == 'SUPER_ADMIN' and hasattr(user, 'super_admin'):
        session_data.update({
            'super_admin_guid': user.super_admin.super_admin_guid_id,
        })
    
    return session_data


class LoginView(View):
    """Handle web login for superadmin and regional admin"""
    template_name = 'esswebapp/index.html'
    
    def get(self, request):
        # If already logged in, redirect to dashboard
        if request.session.get('user_id'):
            return redirect('esswebapp:dashboard')
        form = LoginForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = LoginForm(request.POST)
        
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'error': 'Please fill in all required fields'
            })
        
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        
        try:
            user = User.objects.select_related('role').get(email=email, status=True)
        except User.DoesNotExist:
            return render(request, self.template_name, {
                'form': form,
                'error': 'Invalid credentials'
            })
        
        # Check password using same hashing as APIS app
        if hash_password(password) != user.password:
            return render(request, self.template_name, {
                'form': form,
                'error': 'Invalid credentials'
            })
        
        # Check role - only SUPER_ADMIN and REGIONAL_ADMIN allowed
        role_code = user.role.role_code if user.role else None
        if role_code not in ALLOWED_WEB_ROLES:
            return render(request, self.template_name, {
                'form': form,
                'error': 'Access denied. Only administrators can log in.'
            })
        
        # Save user data in session
        request.session['user'] = get_user_session_data(user)
        request.session.set_expiry(86400)  # 24 hours
        request.session.modified = True
        
        # Update last login time
        user.last_login_time = str(timezone.now())
        user.save(update_fields=['last_login_time'])
        
        return redirect('esswebapp:dashboard')


class LogoutView(View):
    """Handle web logout"""
    
    def get(self, request):
        request.session.flush()
        return redirect('esswebapp:login')
    
    def post(self, request):
        request.session.flush()
        return redirect('esswebapp:login')