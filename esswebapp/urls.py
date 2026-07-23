from django.urls import path
from .views import (
    RootRedirectView, LoginView, LogoutView,
    DashboardView, CentresView, AttendanceView, StudentsView, UsersView,
    FrontendView
)

app_name = 'esswebapp'

urlpatterns = [
    # Root redirect based on auth status
    path('', RootRedirectView.as_view(), name='root'),
    
    # Public routes - traditional form-based login/logout
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Protected routes (require login)
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('centres/', CentresView.as_view(), name='centres'),
    path('attendance/', AttendanceView.as_view(), name='attendance'),
    path('students/', StudentsView.as_view(), name='students'),
    path('users/', UsersView.as_view(), name='users'),
    
    # Catch-all for SPA routing - serves index.html for any unmatched route
    path('<path:undefined_path>', FrontendView.as_view(), name='spa-route'),
]