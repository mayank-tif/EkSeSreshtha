from django.urls import path
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
    path('centres/', CenterView.as_view(), name='centres'),
    path('attendance/', CenterAttendanceView.as_view(), name='attendance'),
    path('students/', StudentsView.as_view(), name='students'),
    path('students/school-dropdown-list/', SchoolDropDownView.as_view(), name='school-dropdown-list'),
    path('school-details-list/', SchoolListView.as_view(), name='school-details-list'),
    path('students/class-list/', ClassListView.as_view(), name='class-list'),
    path('students/student-registration/', StudentRegistrationView.as_view(), name='student-registration'),
    path('students/student-list/', StudentsView.as_view(), name='student-list'),
    path('users/', UsersView.as_view(), name='users'),
    path('users/super-admin/', SuperAdminView.as_view(), name='super-admin'),
    path('users/regional-admin/', RegionalAdminView.as_view(), name='regional-admin'),
    path('users/teacher/', TeacherView.as_view(), name='teacher'),
    
    # Constituency pages
    path('constituency/district/', DistrictView.as_view(), name='district'),
    path('constituency/vidhan-sabha/', VidhanSabhaView.as_view(), name='vidhan-sabha'),
    path('constituency/panchayat/', PanchayatView.as_view(), name='panchayat'),
    path('constituency/village/', VillageView.as_view(), name='village'),
    
    # Attendance center detail page
    path('attendance/center-detail/', AttendanceView.as_view(), name='center-detail'),
    
    # Student attendance history APIs
    path('students/attendance-history/', StudentsView.as_view(), name='student-attendance-history'),
    path('students/monthly-attendance/', StudentsView.as_view(), name='student-monthly-attendance'),
    path('students/daily-attendance/', StudentsView.as_view(), name='student-daily-attendance'),
    
]
