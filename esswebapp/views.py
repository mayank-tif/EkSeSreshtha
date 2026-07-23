from django.shortcuts import render, redirect
from django.views import View

from .auth_views import LoginView, LogoutView


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


class RootRedirectView(View):
    """Redirect root URL based on authentication status"""
    
    def get(self, request):
        if request.session.get('user_id'):
            return redirect('esswebapp:dashboard')
        return redirect('esswebapp:login')


# Protected views using LoginRequiredMixin
class DashboardView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/dashboard.html'
    
    def get(self, request):
        return render(request, self.template_name, {'user': request.web_user})


class CentresView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/centres/educational-centre.html'
    
    def get(self, request):
        return render(request, self.template_name, {'user': request.web_user})


class AttendanceView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/attendance/center-attendance.html'
    
    def get(self, request):
        return render(request, self.template_name, {'user': request.web_user})


class StudentsView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/students/school-list.html'
    
    def get(self, request):
        return render(request, self.template_name, {'user': request.web_user})


class UsersView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/users/super-admin.html'
    
    def get(self, request):
        # Only super admins can access users page
        if not request.web_user.get('is_super_admin'):
            return redirect('esswebapp:dashboard')
        return render(request, self.template_name, {'user': request.web_user})


class FrontendView(View):
    """Serve frontend for SPA routing - catch-all for unmatched routes"""
    template_name = 'esswebapp/index.html'
    
    def get(self, request, undefined_path=None):
        return render(request, self.template_name)