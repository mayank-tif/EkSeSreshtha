from django.urls import path, re_path
from .views import *

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
    path('students/school-list/', StudentsView.as_view(), name='school-list'),
    path('students/student-registration/', StudentsView.as_view(), name='student-registration'),
    path('students/student-list/', StudentsView.as_view(), name='student-list'),
    path('users/', UsersView.as_view(), name='users'),
    path('users/super-admin/', UsersView.as_view(), name='super-admin'),
    path('users/regional-admin/', UsersView.as_view(), name='regional-admin'),
    path('users/teacher/', UsersView.as_view(), name='teacher'),
    
    # Constituency pages
    path('constituency/district/', CentresView.as_view(), name='district'),
    path('constituency/vidhan-sabha/', CentresView.as_view(), name='vidhan-sabha'),
    path('constituency/panchayat/', CentresView.as_view(), name='panchayat'),
    path('constituency/village/', CentresView.as_view(), name='village'),
    
    # Attendance center detail page
    path('attendance/center-detail/', AttendanceView.as_view(), name='center-detail'),
    
]