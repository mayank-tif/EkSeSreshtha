from django.shortcuts import render, redirect
from django.views import View
from django.urls import re_path
from django.utils import timezone
import json

from APIS.models import User, Role
from APIS.utils import hash_password
from .forms import LoginForm


# Allowed role codes for web login
ALLOWED_WEB_ROLES = ['SUPER_ADMIN', 'REGIONAL_ADMIN']


def get_user_json(user_data):
    """Convert user data dict to JSON string safe for HTML attribute"""
    if not user_data:
        return '{}'
    return json.dumps(user_data)


class LoginRequiredMixin:
    """Mixin to require login for class-based views"""
    def dispatch(self, request, *args, **kwargs):
        user_data = request.session.get('user')
        if not user_data:
            return redirect('esswebapp:login')
        
        role_code = user_data.get('role_code')
        if role_code not in ['SUPER_ADMIN', 'REGIONAL_ADMIN']:
            request.session.flush()
            return redirect('esswebapp:login')
        
        # Attach user data to request
        request.web_user = user_data
        return super().dispatch(request, *args, **kwargs)
    

class LoginView(View):
    """Handle web login for superadmin and regional admin"""
    template_name = 'esswebapp/index.html'
    
    def get(self, request):
        # If already logged in, redirect to dashboard
        if request.session.get('user'):
            return redirect('esswebapp:dashboard')
        form = LoginForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        print("request", request.POST)
        form = LoginForm(request.POST)
        
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'error': 'Please fill in all required fields'
            })
        
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        print(email, password)
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
        request.session['user'] = {
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
        request.session.set_expiry(86400)  # 24 hours
        request.session.modified = True
        
        # Update last login time
        user.last_login_time = str(timezone.now())
        user.save(update_fields=['last_login_time'])
        print("user", user)
        
        return redirect('esswebapp:dashboard')


class LogoutView(View):
    """Handle web logout"""
    
    def get(self, request):
        request.session.flush()
        return redirect('esswebapp:login')
    
    def post(self, request):
        request.session.flush()
        return redirect('esswebapp:login')


class RootRedirectView(View):
    """Redirect root URL based on authentication status"""
    
    def get(self, request):
        if request.session.get('user'):
            print("red das")
            return redirect('esswebapp:dashboard')
        print("red log")
        return redirect('esswebapp:login')


# Protected views using LoginRequiredMixin
class DashboardView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/dashboard.html'
    
    def get(self, request):
        print("dash")
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})


class CentresView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/centres/educational-centre.html'
    
    def get(self, request):
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})


class AttendanceView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/attendance/center-attendance.html'
    
    def get(self, request):
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})


class StudentsView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/students/school-list.html'
    
    def get(self, request):
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})


class UsersView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/users/super-admin.html'
    
    def get(self, request):
        # Only super admins can access users page
        if not request.web_user.get('is_super_admin'):
            return redirect('esswebapp:dashboard')
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})