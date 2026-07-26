from django.shortcuts import render, redirect
from django.views import View
from django.urls import re_path
from django.utils import timezone
from django.http import JsonResponse
from django.db import models
from django.db.models import Count
import json
import uuid

from APIS.models import *
from APIS.utils import hash_password
from .forms import LoginForm
import base64
from django.core.files.base import ContentFile


# Allowed role codes for web login
ALLOWED_WEB_ROLES = ['SUPER_ADMIN', 'REGIONAL_ADMIN']

PAGE_SIZE = 50


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


class SuperAdminView(LoginRequiredMixin, View):
    """Super Admin management page + API endpoints"""
    template_name = 'esswebapp/pages/users/super-admin.html'
    
    def get(self, request):
        # Check if it's an AJAX request for JSON data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_super_admins_api(request)
        
        # Only super admins can access
        if not request.web_user.get('is_super_admin'):
            return redirect('esswebapp:dashboard')
        
        # Render the HTML page
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})
    
    def post(self, request):
        # Create new super admin
        return self._create_super_admin(request)
    
    def put(self, request):
        # Update existing super admin
        return self._update_super_admin(request)
    
    def delete(self, request):
        # Soft delete (set status=0)
        return self._delete_super_admin(request)
    
    def _get_super_admins_queryset(self):
        """Get super admins from User model with SUPER_ADMIN role"""
        return User.objects.filter(status=True, role__role_code='SUPER_ADMIN').select_related('role').order_by('-created_on')
    
    def _list_super_admins_api(self, request):
        try:
            sa_id = request.GET.get('id')
            if sa_id:
                try:
                    user = self._get_super_admins_queryset().get(id=sa_id)
                    
                    # Get SuperAdmin profile if exists
                    try:
                        sa = SuperAdmin.objects.get(user=user, status=True)
                        sa_guid = sa.super_admin_guid_id
                        sa_created_by = sa.created_by
                        sa_created_on = sa.created_on
                        sa_updated_by = sa.updated_by
                        sa_updated_on = sa.updated_on
                    except SuperAdmin.DoesNotExist:
                        sa_guid = None
                        sa_created_by = user.created_by
                        sa_created_on = user.created_on
                        sa_updated_by = user.updated_by
                        sa_updated_on = user.updated_on
                    
                    return JsonResponse({
                        'id': user.id,
                        'super_admin_guid_id': sa_guid,
                        'user_id': user.id,
                        'name': user.name,
                        'email': user.email,
                        'phone_number': user.phone_number,
                        'whats_app': user.whats_app,
                        'picture': user.picture.url if user.picture else None,
                        'status': user.status,
                        'enrolment_roll_id': user.enrolment_roll_id,
                        'role_id': user.role_id,
                        'role_code': user.role.role_code if user.role else None,
                        'created_by': sa_created_by,
                        'created_on': sa_created_on.isoformat() if sa_created_on else None,
                        'updated_by': sa_updated_by,
                        'updated_on': sa_updated_on.isoformat() if sa_updated_on else None
                    })
                except User.DoesNotExist:
                    return JsonResponse({'detail': 'Super Admin not found'}, status=404)
            
            queryset = self._get_super_admins_queryset()
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 50))
            search = request.GET.get('search', '').strip().lower()
            
            if search:
                queryset = queryset.filter(
                    models.Q(name__icontains=search) |
                    models.Q(email__icontains=search) |
                    models.Q(phone_number__icontains=search)
                )
            
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            items = []
            for user in queryset[start:end]:
                # Get SuperAdmin profile if exists
                try:
                    sa = SuperAdmin.objects.get(user=user, status=True)
                    sa_guid = sa.super_admin_guid_id
                    sa_created_by = sa.created_by
                    sa_created_on = sa.created_on
                    sa_updated_by = sa.updated_by
                    sa_updated_on = sa.updated_on
                except SuperAdmin.DoesNotExist:
                    sa_guid = None
                    sa_created_by = user.created_by
                    sa_created_on = user.created_on
                    sa_updated_by = user.updated_by
                    sa_updated_on = user.updated_on
                
                items.append({
                    'id': user.id,
                    'super_admin_guid_id': sa_guid,
                    'user_id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'whats_app': user.whats_app,
                    'picture': user.picture.url if user.picture else None,
                    'status': user.status,
                    'enrolment_roll_id': user.enrolment_roll_id,
                    'role_id': user.role_id,
                    'role_code': user.role.role_code if user.role else None,
                    'created_by': sa_created_by,
                    'created_on': sa_created_on.isoformat() if sa_created_on else None,
                    'updated_by': sa_updated_by,
                    'updated_on': sa_updated_on.isoformat() if sa_updated_on else None
                })
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _create_super_admin(self, request):
        try:
            data = json.loads(request.body)
            
            name = data.get('name', '').strip()
            email = data.get('email', '').strip().lower()
            phone = data.get('phone_number', '').strip()
            whats_app = data.get('whats_app', '').strip()
            password = data.get('password', '').strip()
            enrolment_roll_id = data.get('enrolment_roll_id', '').strip()
            
            if not name:
                return JsonResponse({'detail': 'Name is required'}, status=400)
            if not email:
                return JsonResponse({'detail': 'Email is required'}, status=400)
            if not password:
                return JsonResponse({'detail': 'Password is required'}, status=400)
            
            # Check for duplicates
            if User.objects.filter(email=email).exists():
                return JsonResponse({'detail': 'Email already exists'}, status=400)
            if phone and User.objects.filter(phone_number=phone).exists():
                return JsonResponse({'detail': 'Phone number already exists'}, status=400)
            if enrolment_roll_id and User.objects.filter(enrolment_roll_id=enrolment_roll_id).exists():
                return JsonResponse({'detail': 'Enrolment roll ID already exists'}, status=400)
            
            # Get SUPER_ADMIN role
            super_admin_role = Role.objects.filter(role_code='SUPER_ADMIN', status=True).first()
            if not super_admin_role:
                return JsonResponse({'detail': 'SUPER_ADMIN role not configured'}, status=500)
            
            # Handle picture (base64 data URL)
            picture_data = data.get('picture', '').strip()
            picture_file = None
            if picture_data and picture_data.startswith('data:'):
                import base64
                from django.core.files.base import ContentFile
                format, imgstr = picture_data.split(';base64,')
                ext = format.split('/')[-1]
                picture_file = ContentFile(base64.b64decode(imgstr), name=f'profile_{uuid.uuid4().hex[:8]}.{ext}')
            
            # Create user
            user = User.objects.create(
                name=name,
                email=email,
                phone_number=phone if phone else None,
                whats_app=whats_app if whats_app else None,
                password=hash_password(password),  
                enrolment_roll_id=enrolment_roll_id if enrolment_roll_id else None,
                role=super_admin_role,
                status=True,
                created_by=request.web_user.get('user_id'),
                created_on=timezone.now()
            )
            
            # Save picture if provided
            if picture_file:
                user.picture.save(picture_file.name, picture_file, save=True)
            
            # Create SuperAdmin profile
            sa = SuperAdmin.objects.create(
                super_admin_guid_id=str(uuid.uuid4()),
                user=user,
                status=True,
                created_by=request.web_user.get('user_id'),
                created_on=timezone.now()
            )
            
            return JsonResponse({
                'id': user.id,  # Use user.id as the main ID
                'super_admin_guid_id': sa.super_admin_guid_id,
                'user_id': user.id,
                'name': user.name,
                'email': user.email,
                'phone_number': user.phone_number,
                'whats_app': user.whats_app,
                'status': user.status,
                'enrolment_roll_id': user.enrolment_roll_id,
                'role_code': user.role.role_code,
                'created_by': sa.created_by,
                'created_on': sa.created_on.isoformat() if sa.created_on else None,
                'message': 'Super Admin created successfully'
            }, status=201)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _update_super_admin(self, request):
        try:
            data = json.loads(request.body)
            user_id = data.get('id')  # This is now user_id
            
            if not user_id:
                return JsonResponse({'detail': 'ID is required'}, status=400)
            
            try:
                user = User.objects.get(id=user_id, role__role_code='SUPER_ADMIN', status=True)
                sa = SuperAdmin.objects.get(user=user, status=True)
            except (User.DoesNotExist, SuperAdmin.DoesNotExist):
                return JsonResponse({'detail': 'Super Admin not found'}, status=404)
            
            name = data.get('name', '').strip()
            email = data.get('email', '').strip().lower()
            phone = data.get('phone_number', '').strip()
            whats_app = data.get('whats_app', '').strip()
            enrolment_roll_id = data.get('enrolment_roll_id', '').strip()
            password = data.get('password', '').strip()  # Optional password update
            
            if not name:
                return JsonResponse({'detail': 'Name is required'}, status=400)
            if not email:
                return JsonResponse({'detail': 'Email is required'}, status=400)
            
            # Check for duplicates (excluding current user)
            if User.objects.filter(email=email).exclude(id=user_id).exists():
                return JsonResponse({'detail': 'Email already exists'}, status=400)
            if phone and User.objects.filter(phone_number=phone).exclude(id=user_id).exists():
                return JsonResponse({'detail': 'Phone number already exists'}, status=400)
            if enrolment_roll_id and User.objects.filter(enrolment_roll_id=enrolment_roll_id).exclude(id=user_id).exists():
                return JsonResponse({'detail': 'Enrolment roll ID already exists'}, status=400)
            
            # Update user
            user.name = name
            user.email = email
            user.phone_number = phone if phone else None
            user.whats_app = whats_app if whats_app else None
            if enrolment_roll_id:
                user.enrolment_roll_id = enrolment_roll_id
            
            # Update password only if provided and not blank
            if password:
                user.password = hash_password(password)
            
            # Handle picture (base64 data URL)
            picture_data = data.get('picture', '').strip()
            if picture_data and picture_data.startswith('data:'):
                import base64
                from django.core.files.base import ContentFile
                format, imgstr = picture_data.split(';base64,')
                ext = format.split('/')[-1]
                picture_file = ContentFile(base64.b64decode(imgstr), name=f'profile_{uuid.uuid4().hex[:8]}.{ext}')
                user.picture.save(picture_file.name, picture_file, save=False)
            
            user.updated_by = request.web_user.get('user_id')
            user.updated_on = timezone.now()
            user.save()
            
            # Update super admin
            sa.updated_by = request.web_user.get('user_id')
            sa.updated_on = timezone.now()
            sa.save()
            
            return JsonResponse({
                'id': user.id,  # Use user.id as the main ID
                'super_admin_guid_id': sa.super_admin_guid_id,
                'user_id': user.id,
                'name': user.name,
                'email': user.email,
                'phone_number': user.phone_number,
                'whats_app': user.whats_app,
                'status': user.status,
                'enrolment_roll_id': user.enrolment_roll_id,
                'role_code': user.role.role_code if user.role else None,
                'message': 'Super Admin updated successfully'
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _delete_super_admin(self, request):
        try:
            import json
            data = json.loads(request.body)
            user_id = data.get('id')  # This is now user_id
            
            if not user_id:
                return JsonResponse({'detail': 'ID is required'}, status=400)
            
            try:
                user = User.objects.get(id=user_id, role__role_code='SUPER_ADMIN')
                sa = SuperAdmin.objects.get(user=user)
            except (User.DoesNotExist, SuperAdmin.DoesNotExist):
                return JsonResponse({'detail': 'Super Admin not found'}, status=404)
            
            # Soft delete - set status to False
            sa.status = False
            sa.updated_by = request.web_user.get('user_id')
            sa.updated_on = timezone.now()
            sa.save()
            
            # Also deactivate user
            user.status = False
            user.updated_by = request.web_user.get('user_id')
            user.updated_on = timezone.now()
            user.save()
            
            return JsonResponse({'message': 'Super Admin deactivated successfully'})
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)



class RegionalAdminView(LoginRequiredMixin, View):
    """Regional Admin management page + API endpoints"""
    template_name = 'esswebapp/pages/users/regional-admin.html'
    
    def get(self, request):
        # Check if it's an AJAX request for JSON data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_regional_admins_api(request)
        
        # Only super admins can access
        if not request.web_user.get('is_super_admin'):
            return redirect('esswebapp:dashboard')
        
        # Render the HTML page
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})
    
    def post(self, request):
        # Create new regional admin
        return self._create_regional_admin(request)
    
    def put(self, request):
        # Update existing regional admin
        return self._update_regional_admin(request)
    
    def delete(self, request):
        # Soft delete (set status=0)
        return self._delete_regional_admin(request)
    
    def _get_regional_admins_queryset(self):
        """Get regional admins from User model with REGIONAL_ADMIN role"""
        return User.objects.filter(status=True, role__role_code='REGIONAL_ADMIN').select_related('role').order_by('-created_on')
    
    def _list_regional_admins_api(self, request):
        try:
            ra_id = request.GET.get('id')
            print("ra_id", ra_id)
            if ra_id:
                try:
                    user = self._get_regional_admins_queryset().get(id=ra_id)
                    
                    # Get RegionalAdmin profile if exists
                    try:
                        ra = RegionalAdmin.objects.select_related('district', 'vidhan_sabha', 'panchayat', 'village').get(user=user, status=True)
                        print("ra", ra)
                        ra_guid = ra.regional_admin_guid_id
                        ra_district = ra.district_id
                        ra_district_name = ra.district.name if ra.district else None
                        ra_vidhan_sabha = ra.vidhan_sabha_id
                        ra_vidhan_sabha_name = ra.vidhan_sabha.name if ra.vidhan_sabha else None
                        ra_panchayat = ra.panchayat_id
                        ra_panchayat_name = ra.panchayat.name if ra.panchayat else None
                        ra_village = ra.village_id
                        ra_village_name = ra.village.name if ra.village else None
                        ra_age = ra.age
                        ra_gender = ra.gender
                        ra_dob = ra.date_of_birth
                        ra_contact = ra.contact
                        ra_address = ra.full_address
                        ra_education = ra.education
                        ra_guardian_name = ra.guardian_name
                        ra_guardian_number = ra.guardian_number
                        ra_created_by = ra.created_by
                        ra_created_on = ra.created_on
                        ra_updated_by = ra.updated_by
                        ra_updated_on = ra.updated_on
                        ra_enrollment_date = ra.enrollment_date
                    except RegionalAdmin.DoesNotExist:
                        ra_guid = None
                        ra_district = None
                        ra_district_name = None
                        ra_vidhan_sabha = None
                        ra_vidhan_sabha_name = None
                        ra_panchayat = None
                        ra_panchayat_name = None
                        ra_village = None
                        ra_village_name = None
                        ra_age = None
                        ra_gender = None
                        ra_dob = None
                        ra_contact = None
                        ra_address = None
                        ra_education = None
                        ra_guardian_name = None
                        ra_guardian_number = None
                        ra_created_by = user.created_by
                        ra_created_on = user.created_on
                        ra_updated_by = user.updated_by
                        ra_updated_on = user.updated_on
                    
                    return JsonResponse({
                        'id': user.id,
                        'regional_admin_guid_id': ra_guid,
                        'user_id': user.id,
                        'name': user.name,
                        'email': user.email,
                        'phone_number': user.phone_number,
                        'whats_app': user.whats_app,
                        'picture': user.picture.url if user.picture else None,
                        'status': user.status,
                        'enrolment_roll_id': user.enrolment_roll_id,
                        'role_id': user.role_id,
                        'role_code': user.role.role_code if user.role else None,
                        'district_id': ra_district,
                        'district_name': ra_district_name,
                        'vidhan_sabha_id': ra_vidhan_sabha,
                        'vidhan_sabha_name': ra_vidhan_sabha_name,
                        'panchayat_id': ra_panchayat,
                        'panchayat_name': ra_panchayat_name,
                        'village_id': ra_village,
                        'village_name': ra_village_name,
                        'age': ra_age,
                        'gender': ra_gender,
                        'date_of_birth': ra_dob,
                        'contact': ra_contact,
                        'full_address': ra_address,
                        'education': ra_education,
                        'guardian_name': ra_guardian_name,
                        'guardian_number': ra_guardian_number,
                        'created_by': ra_created_by,
                        'created_on': ra_created_on.isoformat() if ra_created_on else None,
                        'updated_by': ra_updated_by,
                        'updated_on': ra_updated_on.isoformat() if ra_updated_on else None,
                        'enrollment_date': ra_enrollment_date if ra_enrollment_date else None
                    })
                except User.DoesNotExist:
                    return JsonResponse({'detail': 'Regional Admin not found'}, status=404)
            
            queryset = self._get_regional_admins_queryset()
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 50))
            search = request.GET.get('search', '').strip().lower()
            
            if search:
                queryset = queryset.filter(
                    models.Q(name__icontains=search) |
                    models.Q(email__icontains=search) |
                    models.Q(phone_number__icontains=search)
                )
            
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            items = []
            for user in queryset[start:end]:
                # Get RegionalAdmin profile if exists
                try:
                    ra = RegionalAdmin.objects.select_related('district', 'vidhan_sabha', 'panchayat', 'village').get(user=user, status=True)
                    ra_guid = ra.regional_admin_guid_id
                    ra_district = ra.district_id
                    ra_district_name = ra.district.name if ra.district else None
                    ra_vidhan_sabha = ra.vidhan_sabha_id
                    ra_vidhan_sabha_name = ra.vidhan_sabha.name if ra.vidhan_sabha else None
                    ra_panchayat = ra.panchayat_id
                    ra_panchayat_name = ra.panchayat.name if ra.panchayat else None
                    ra_village = ra.village_id
                    ra_village_name = ra.village.name if ra.village else None
                    ra_age = ra.age
                    ra_gender = ra.gender
                    ra_dob = ra.date_of_birth
                    ra_contact = ra.contact
                    ra_address = ra.full_address
                    ra_education = ra.education
                    ra_guardian_name = ra.guardian_name
                    ra_guardian_number = ra.guardian_number
                    ra_created_by = ra.created_by
                    ra_created_on = ra.created_on
                    ra_updated_by = ra.updated_by
                    ra_updated_on = ra.updated_on
                except RegionalAdmin.DoesNotExist:
                    ra_guid = None
                    ra_district = None
                    ra_district_name = None
                    ra_vidhan_sabha = None
                    ra_vidhan_sabha_name = None
                    ra_panchayat = None
                    ra_panchayat_name = None
                    ra_village = None
                    ra_village_name = None
                    ra_age = None
                    ra_gender = None
                    ra_dob = None
                    ra_contact = None
                    ra_address = None
                    ra_education = None
                    ra_guardian_name = None
                    ra_guardian_number = None
                    ra_created_by = user.created_by
                    ra_created_on = user.created_on
                    ra_updated_by = user.updated_by
                    ra_updated_on = user.updated_on
                
                items.append({
                    'id': user.id,
                    'regional_admin_guid_id': ra_guid,
                    'user_id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'whats_app': user.whats_app,
                    'picture': user.picture.url if user.picture else None,
                    'status': user.status,
                    'enrolment_roll_id': user.enrolment_roll_id,
                    'role_id': user.role_id,
                    'role_code': user.role.role_code if user.role else None,
                    'district_id': ra_district,
                    'district_name': ra_district_name,
                    'vidhan_sabha_id': ra_vidhan_sabha,
                    'vidhan_sabha_name': ra_vidhan_sabha_name,
                    'panchayat_id': ra_panchayat,
                    'panchayat_name': ra_panchayat_name,
                    'village_id': ra_village,
                    'village_name': ra_village_name,
                    'age': ra_age,
                    'gender': ra_gender,
                    'date_of_birth': ra_dob,
                    'contact': ra_contact,
                    'full_address': ra_address,
                    'education': ra_education,
                    'guardian_name': ra_guardian_name,
                    'guardian_number': ra_guardian_number,
                    'created_by': ra_created_by,
                    'created_on': ra_created_on.isoformat() if ra_created_on else None,
                    'updated_by': ra_updated_by,
                    'updated_on': ra_updated_on.isoformat() if ra_updated_on else None
                })
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _create_regional_admin(self, request):
        try:
            data = json.loads(request.body)
            print("data", data)
            
            name = data.get('name', '').strip()
            email = data.get('email', '').strip().lower()
            phone = data.get('phone_number', '').strip()
            whats_app = data.get('whats_app', '').strip()
            password = data.get('password', '').strip()
            enrolment_roll_id = data.get('enrolment_roll_id', '').strip()
            district_id = data.get('district_id')
            vidhan_sabha_id = data.get('vidhan_sabha_id')
            panchayat_id = data.get('panchayat_id')
            village_id = data.get('village_id')
            age = data.get('age')
            gender = data.get('gender', '').strip()
            date_of_birth = data.get('date_of_birth', '').strip()
            contact = data.get('contact', '').strip()
            full_address = data.get('full_address', '').strip()
            education = data.get('education', '').strip()
            guardian_name = data.get('guardian_name', '').strip()
            guardian_number = data.get('guardian_number', '').strip()
            enrollment_date = data.get('enrollment_date', '').strip()
            
            if not name:
                return JsonResponse({'detail': 'Name is required'}, status=400)
            if not email:
                return JsonResponse({'detail': 'Email is required'}, status=400)
            if not password:
                return JsonResponse({'detail': 'Password is required'}, status=400)
            
            # Check for duplicates
            if User.objects.filter(email=email).exists():
                return JsonResponse({'detail': 'Email already exists'}, status=400)
            if phone and User.objects.filter(phone_number=phone).exists():
                return JsonResponse({'detail': 'Phone number already exists'}, status=400)
            if enrolment_roll_id and User.objects.filter(enrolment_roll_id=enrolment_roll_id).exists():
                return JsonResponse({'detail': 'Enrolment roll ID already exists'}, status=400)
            
            # Get REGIONAL_ADMIN role
            regional_admin_role = Role.objects.filter(role_code='REGIONAL_ADMIN', status=True).first()
            if not regional_admin_role:
                return JsonResponse({'detail': 'REGIONAL_ADMIN role not configured'}, status=500)
            
            # Handle picture (base64 data URL)
            picture_data = data.get('picture', '').strip()
            picture_file = None
            if picture_data and picture_data.startswith('data:'):
                format, imgstr = picture_data.split(';base64,')
                ext = format.split('/')[-1]
                picture_file = ContentFile(base64.b64decode(imgstr), name=f'profile_{uuid.uuid4().hex[:8]}.{ext}')
            
            # Create user
            user = User.objects.create(
                name=name,
                email=email,
                phone_number=phone if phone else None,
                whats_app=whats_app if whats_app else None,
                password=hash_password(password),  
                enrolment_roll_id=enrolment_roll_id if enrolment_roll_id else None,
                role=regional_admin_role,
                status=True,
                created_by=request.web_user.get('user_id'),
                created_on=timezone.now()
            )
            
            # Save picture if provided
            if picture_file:
                user.picture.save(picture_file.name, picture_file, save=True)
                
            print("ra user", user)
            
            # Create RegionalAdmin profile
            ra = RegionalAdmin.objects.create(
                regional_admin_guid_id=str(uuid.uuid4()),
                user=user,
                district_id=district_id if district_id else None,
                vidhan_sabha_id=vidhan_sabha_id if vidhan_sabha_id else None,
                panchayat_id=panchayat_id if panchayat_id else None,
                village_id=village_id if village_id else None,
                age=age if age else None,
                gender=gender if gender else None,
                date_of_birth=date_of_birth if date_of_birth else None,
                contact=contact if contact else None,
                full_address=full_address if full_address else None,
                education=education if education else None,
                guardian_name=guardian_name if guardian_name else None,
                guardian_number=guardian_number if guardian_number else None,
                status=True,
                enrollment_date=enrollment_date,
                created_by=request.web_user.get('user_id'),
                created_on=timezone.now()
            )
            print("ra", ra)
            
            return JsonResponse({
                'id': user.id,
                'regional_admin_guid_id': ra.regional_admin_guid_id,
                'user_id': user.id,
                'name': user.name,
                'email': user.email,
                'phone_number': user.phone_number,
                'whats_app': user.whats_app,
                'status': user.status,
                'enrolment_roll_id': user.enrolment_roll_id,
                'role_code': user.role.role_code,
                'district_id': ra.district_id,
                'vidhan_sabha_id': ra.vidhan_sabha_id,
                'panchayat_id': ra.panchayat_id,
                'village_id': ra.village_id,
                'message': 'Regional Admin created successfully'
            }, status=201)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _update_regional_admin(self, request):
        try:
            data = json.loads(request.body)
            user_id = data.get('id')  # This is now user_id
            
            if not user_id:
                return JsonResponse({'detail': 'ID is required'}, status=400)
            
            try:
                user = User.objects.get(id=user_id, role__role_code='REGIONAL_ADMIN', status=True)
                ra = RegionalAdmin.objects.get(user=user, status=True)
            except (User.DoesNotExist, RegionalAdmin.DoesNotExist):
                return JsonResponse({'detail': 'Regional Admin not found'}, status=404)
            
            name = data.get('name', '').strip()
            email = data.get('email', '').strip().lower()
            phone = data.get('phone_number', '').strip()
            whats_app = data.get('whats_app', '').strip()
            enrolment_roll_id = data.get('enrolment_roll_id', '').strip()
            district_id = data.get('district_id')
            vidhan_sabha_id = data.get('vidhan_sabha_id')
            panchayat_id = data.get('panchayat_id')
            village_id = data.get('village_id')
            age = data.get('age')
            gender = data.get('gender', '').strip()
            date_of_birth = data.get('date_of_birth', '').strip()
            contact = data.get('contact', '').strip()
            full_address = data.get('full_address', '').strip()
            education = data.get('education', '').strip()
            guardian_name = data.get('guardian_name', '').strip()
            guardian_number = data.get('guardian_number', '').strip()
            password = data.get('password', '').strip()  # Optional password update
            
            if not name:
                return JsonResponse({'detail': 'Name is required'}, status=400)
            if not email:
                return JsonResponse({'detail': 'Email is required'}, status=400)
            
            # Check for duplicates (excluding current user)
            if User.objects.filter(email=email).exclude(id=user_id).exists():
                return JsonResponse({'detail': 'Email already exists'}, status=400)
            if phone and User.objects.filter(phone_number=phone).exclude(id=user_id).exists():
                return JsonResponse({'detail': 'Phone number already exists'}, status=400)
            if enrolment_roll_id and User.objects.filter(enrolment_roll_id=enrolment_roll_id).exclude(id=user_id).exists():
                return JsonResponse({'detail': 'Enrolment roll ID already exists'}, status=400)
            
            # Update user
            user.name = name
            user.email = email
            user.phone_number = phone if phone else None
            user.whats_app = whats_app if whats_app else None
            if enrolment_roll_id:
                user.enrolment_roll_id = enrolment_roll_id
            
            # Update password only if provided and not blank
            if password:
                user.password = hash_password(password)
            
            # Handle picture (base64 data URL)
            picture_data = data.get('picture', '').strip()
            if picture_data and picture_data.startswith('data:'):
                import base64
                from django.core.files.base import ContentFile
                import uuid
                format, imgstr = picture_data.split(';base64,')
                ext = format.split('/')[-1]
                picture_file = ContentFile(base64.b64decode(imgstr), name=f'profile_{uuid.uuid4().hex[:8]}.{ext}')
                user.picture.save(picture_file.name, picture_file, save=False)
            
            user.updated_by = request.web_user.get('user_id')
            user.updated_on = timezone.now()
            user.save()
            
            # Update regional admin
            ra.district_id = district_id if district_id else None
            ra.vidhan_sabha_id = vidhan_sabha_id if vidhan_sabha_id else None
            ra.panchayat_id = panchayat_id if panchayat_id else None
            ra.village_id = village_id if village_id else None
            ra.age = age if age else None
            ra.gender = gender if gender else None
            ra.date_of_birth = date_of_birth if date_of_birth else None
            ra.contact = contact if contact else None
            ra.full_address = full_address if full_address else None
            ra.education = education if education else None
            ra.guardian_name = guardian_name if guardian_name else None
            ra.guardian_number = guardian_number if guardian_number else None
            ra.updated_by = request.web_user.get('user_id')
            ra.updated_on = timezone.now()
            ra.save()
            
            return JsonResponse({
                'id': user.id,  # Use user.id as the main ID
                'regional_admin_guid_id': ra.regional_admin_guid_id,
                'user_id': user.id,
                'name': user.name,
                'email': user.email,
                'phone_number': user.phone_number,
                'whats_app': user.whats_app,
                'status': user.status,
                'enrolment_roll_id': user.enrolment_roll_id,
                'role_code': user.role.role_code if user.role else None,
                'district_id': ra.district_id,
                'vidhan_sabha_id': ra.vidhan_sabha_id,
                'panchayat_id': ra.panchayat_id,
                'village_id': ra.village_id,
                'message': 'Regional Admin updated successfully'
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _delete_regional_admin(self, request):
        try:
            data = json.loads(request.body)
            user_id = data.get('id')  # This is now user_id
            
            if not user_id:
                return JsonResponse({'detail': 'ID is required'}, status=400)
            
            try:
                user = User.objects.get(id=user_id, role__role_code='REGIONAL_ADMIN')
                ra = RegionalAdmin.objects.get(user=user)
            except (User.DoesNotExist, RegionalAdmin.DoesNotExist):
                return JsonResponse({'detail': 'Regional Admin not found'}, status=404)
            
            # Soft delete - set status to False
            ra.status = False
            ra.updated_by = request.web_user.get('user_id')
            ra.updated_on = timezone.now()
            ra.save()
            
            # Also deactivate user
            user.status = False
            user.updated_by = request.web_user.get('user_id')
            user.updated_on = timezone.now()
            user.save()
            
            return JsonResponse({'message': 'Regional Admin deactivated successfully'})
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)



class DistrictView(LoginRequiredMixin, View):
    """District management page + API endpoints"""
    template_name = 'esswebapp/pages/constituency/district.html'
    
    def get(self, request):
        # Check if it's an AJAX request for JSON data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_districts_api(request)
        
        # Render the HTML page
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})
    
    def post(self, request):
        # Create new district
        return self._create_district(request)
    
    def put(self, request):
        # Update existing district
        return self._update_district(request)
    
    def delete(self, request):
        # Soft delete (set status=0)
        return self._delete_district(request)
    
    def _get_districts_queryset(self):
        """Get districts ordered by created_on desc"""
        return District.objects.filter(status=True).order_by('-created_on')
    
    def _list_districts_api(self, request):
        """Return paginated districts as JSON for DataTables, or single district if id provided"""
        try:
            
            # If id is provided, return single district
            district_id = request.GET.get('id')
            if district_id:
                try:
                    district = District.objects.filter(status=True).annotate(
                        vidhan_sabha_count=Count('vidhan_sabhas', filter=models.Q(vidhan_sabhas__status=True)),
                        panchayat_count=Count('panchayats', filter=models.Q(panchayats__status=True))
                    ).get(id=district_id)

                    return JsonResponse({
                        'id': district.id,
                        'district_guid_id': district.district_guid_id,
                        'name': district.name,
                        'status': district.status,
                        'created_by': district.created_by,
                        'created_on': district.created_on.isoformat() if district.created_on else None,
                        'updated_by': district.updated_by,
                        'updated_on': district.updated_on.isoformat() if district.updated_on else None,
                        'vidhan_sabha_count': district.vidhan_sabha_count,
                        'panchayat_count': district.panchayat_count
                    })
                except District.DoesNotExist:
                    return JsonResponse({'detail': 'District not found'}, status=404)
            
            # Otherwise return paginated list
            districts = self._get_districts_queryset()
            
            # Add related counts
            districts = districts.annotate(
                vidhan_sabha_count=Count('vidhan_sabhas', filter=models.Q(vidhan_sabhas__status=True)),
                panchayat_count=Count('panchayats', filter=models.Q(panchayats__status=True))
            )
            
            # Pagination params
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', PAGE_SIZE))
            search = request.GET.get('search', '').strip().lower()
            
            if search:
                districts = districts.filter(
                    models.Q(name__icontains=search)
                )
            
            total = districts.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            items = []
            for d in districts[start:end]:
                items.append({
                    'id': d.id,
                    'district_guid_id': d.district_guid_id,
                    'name': d.name,
                    'status': d.status,
                    'created_by': d.created_by,
                    'created_on': d.created_on.isoformat() if d.created_on else None,
                    'updated_by': d.updated_by,
                    'updated_on': d.updated_on.isoformat() if d.updated_on else None,
                    'vidhan_sabha_count': d.vidhan_sabha_count,
                    'panchayat_count': d.panchayat_count
                })
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _create_district(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            
            if not name:
                return JsonResponse({'detail': 'District name is required'}, status=400)
            
            # Check if district with same name exists
            if District.objects.filter(name__iexact=name, status=True).exists():
                return JsonResponse({'detail': 'A district with this name already exists'}, status=400)
            
            # Get user ID from session
            user_id = request.web_user.get('user_id')
            
            # Generate GUID
            district_guid = str(uuid.uuid4())
            
            district = District.objects.create(
                district_guid_id=district_guid,
                name=name,
                status=True,
                created_by=user_id,
                created_on=timezone.now(),
                updated_by=user_id,
                updated_on=timezone.now()
            )
            
            # Return created district with related counts
            return JsonResponse({
                'id': district.id,
                'district_guid_id': district.district_guid_id,
                'name': district.name,
                'status': district.status,
                'created_by': district.created_by,
                'created_on': district.created_on,
                'vidhan_sabha_count': 0,
                'panchayat_count': 0
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _update_district(self, request):
        try:
            data = json.loads(request.body)
            district_id = data.get('id')
            name = data.get('name', '').strip()
            
            if not district_id:
                return JsonResponse({'detail': 'District ID is required'}, status=400)
            
            if not name:
                return JsonResponse({'detail': 'District name is required'}, status=400)
            
            try:
                district = District.objects.get(id=district_id, status=True)
            except District.DoesNotExist:
                return JsonResponse({'detail': 'District not found'}, status=404)
            
            # Check if another district with same name exists
            if District.objects.filter(name__iexact=name, status=True).exclude(id=district_id).exists():
                return JsonResponse({'detail': 'A district with this name already exists'}, status=400)
            
            user_id = request.web_user.get('user_id')
            
            district.name = name
            district.updated_by = user_id
            district.updated_on = timezone.now()
            district.save(update_fields=['name', 'updated_by', 'updated_on'])
            
            # Return updated district with related counts
            return JsonResponse({
                'id': district.id,
                'district_guid_id': district.district_guid_id,
                'name': district.name,
                'status': district.status,
                'updated_by': district.updated_by,
                'updated_on': district.updated_on,
                'vidhan_sabha_count': district.vidhan_sabhas.filter(status=True).count(),
                'panchayat_count': district.panchayats.filter(status=True).count()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _delete_district(self, request):
        try:
            # Get ID from query params or body
            district_id = request.GET.get('id')
            if not district_id:
                try:
                    data = json.loads(request.body)
                    district_id = data.get('id')
                except:
                    pass
            
            if not district_id:
                return JsonResponse({'detail': 'District ID is required'}, status=400)
            
            try:
                district = District.objects.get(id=district_id, status=True)
            except District.DoesNotExist:
                return JsonResponse({'detail': 'District not found'}, status=404)
            
            # Soft delete - set status to False (0)
            district.status = False
            district.updated_by = request.web_user.get('user_id')
            district.updated_on = timezone.now()
            district.save(update_fields=['status', 'updated_by', 'updated_on'])
            
            return JsonResponse({'detail': 'District deleted successfully'})
            
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)


class VidhanSabhaView(LoginRequiredMixin, View):
    """Vidhan Sabha management page + API endpoints"""
    template_name = 'esswebapp/pages/constituency/vidhan-sabha.html'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_vidhan_sabha_api(request)
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})
    
    def post(self, request):
        return self._create_vidhan_sabha(request)
    
    def put(self, request):
        return self._update_vidhan_sabha(request)
    
    def delete(self, request):
        return self._delete_vidhan_sabha(request)
    
    def _get_vidhan_sabha_queryset(self):
        return VidhanSabha.objects.filter(status=True).select_related('district').order_by('-created_on')
    
    def _list_vidhan_sabha_api(self, request):
        try:
            
            # If id is provided, return single vidhan sabha
            vs_id = request.GET.get('id')
            if vs_id:
                try:
                    vs = VidhanSabha.objects.filter(status=True).select_related('district').annotate(
                        panchayat_count=Count('panchayats', filter=models.Q(panchayats__status=True))
                    ).get(id=vs_id)
                    
                    return JsonResponse({
                        'id': vs.id,
                        'vidhan_sabha_guid_id': vs.vidhan_sabha_guid_id,
                        'name': vs.name,
                        'status': vs.status,
                        'district_id': vs.district_id,
                        'district_name': vs.district.name if vs.district else None,
                        'created_by': vs.created_by,
                        'created_on': vs.created_on.isoformat() if vs.created_on else None,
                        'updated_by': vs.updated_by,
                        'updated_on': vs.updated_on.isoformat() if vs.updated_on else None,
                        'panchayat_count': vs.panchayat_count
                    })
                except VidhanSabha.DoesNotExist:
                    return JsonResponse({'detail': 'Vidhan Sabha not found'}, status=404)
            
            # Otherwise return paginated list
            queryset = self._get_vidhan_sabha_queryset()
            
            # Filter by district if provided (for cascading dropdowns)
            district_id = request.GET.get('district_id')
            if district_id:
                queryset = queryset.filter(district_id=district_id)
            
            # Add panchayat count
            queryset = queryset.annotate(
                panchayat_count=Count('panchayats', filter=models.Q(panchayats__status=True))
            )
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', PAGE_SIZE))
            search = request.GET.get('search', '').strip().lower()
            
            if search:
                queryset = queryset.filter(models.Q(name__icontains=search))
            
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            items = []
            for vs in queryset[start:end]:
                items.append({
                    'id': vs.id,
                    'vidhan_sabha_guid_id': vs.vidhan_sabha_guid_id,
                    'name': vs.name,
                    'status': vs.status,
                    'district_id': vs.district_id,
                    'district_name': vs.district.name if vs.district else None,
                    'created_by': vs.created_by,
                    'created_on': vs.created_on.isoformat() if vs.created_on else None,
                    'updated_by': vs.updated_by,
                    'updated_on': vs.updated_on.isoformat() if vs.updated_on else None,
                    'panchayat_count': vs.panchayat_count
                })
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _create_vidhan_sabha(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            district_id = data.get('district_id')
            
            if not name:
                return JsonResponse({'detail': 'Vidhan Sabha name is required'}, status=400)
            if not district_id:
                return JsonResponse({'detail': 'District is required'}, status=400)
            
            if VidhanSabha.objects.filter(name__iexact=name, district_id=district_id, status=True).exists():
                return JsonResponse({'detail': 'A Vidhan Sabha with this name already exists in this district'}, status=400)
            
            user_id = request.web_user.get('user_id')
            vs_guid = str(uuid.uuid4())
            
            vs = VidhanSabha.objects.create(
                vidhan_sabha_guid_id=vs_guid,
                name=name,
                district_id=district_id,
                status=True,
                created_by=user_id,
                created_on=timezone.now(),
                updated_by=user_id,
                updated_on=timezone.now()
            )
            
            return JsonResponse({
                'id': vs.id,
                'vidhan_sabha_guid_id': vs.vidhan_sabha_guid_id,
                'name': vs.name,
                'status': vs.status,
                'district_id': vs.district_id,
                'district_name': vs.district.name if vs.district else None,
                'created_by': vs.created_by,
                'created_on': vs.created_on,
                'panchayat_count': 0
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _update_vidhan_sabha(self, request):
        try:
            data = json.loads(request.body)
            vs_id = data.get('id')
            name = data.get('name', '').strip()
            district_id = data.get('district_id')
            
            if not vs_id:
                return JsonResponse({'detail': 'Vidhan Sabha ID is required'}, status=400)
            if not name:
                return JsonResponse({'detail': 'Vidhan Sabha name is required'}, status=400)
            if not district_id:
                return JsonResponse({'detail': 'District is required'}, status=400)
            
            try:
                vs = VidhanSabha.objects.get(id=vs_id, status=True)
            except VidhanSabha.DoesNotExist:
                return JsonResponse({'detail': 'Vidhan Sabha not found'}, status=404)
            
            if VidhanSabha.objects.filter(name__iexact=name, district_id=district_id, status=True).exclude(id=vs_id).exists():
                return JsonResponse({'detail': 'A Vidhan Sabha with this name already exists in this district'}, status=400)
            
            user_id = request.web_user.get('user_id')
            vs.name = name
            vs.district_id = district_id
            vs.updated_by = user_id
            vs.updated_on = timezone.now()
            vs.save(update_fields=['name', 'district_id', 'updated_by', 'updated_on'])
            
            return JsonResponse({
                'id': vs.id,
                'vidhan_sabha_guid_id': vs.vidhan_sabha_guid_id,
                'name': vs.name,
                'status': vs.status,
                'district_id': vs.district_id,
                'district_name': vs.district.name if vs.district else None,
                'updated_by': vs.updated_by,
                'updated_on': vs.updated_on,
                'panchayat_count': vs.panchayats.filter(status=True).count()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _delete_vidhan_sabha(self, request):
        try:
            vs_id = request.GET.get('id')
            if not vs_id:
                try:
                    data = json.loads(request.body)
                    vs_id = data.get('id')
                except:
                    pass
            
            if not vs_id:
                return JsonResponse({'detail': 'Vidhan Sabha ID is required'}, status=400)
            
            try:
                vs = VidhanSabha.objects.get(id=vs_id, status=True)
            except VidhanSabha.DoesNotExist:
                return JsonResponse({'detail': 'Vidhan Sabha not found'}, status=404)
            
            vs.status = False
            vs.updated_by = request.web_user.get('user_id')
            vs.updated_on = timezone.now()
            vs.save(update_fields=['status', 'updated_by', 'updated_on'])
            
            return JsonResponse({'detail': 'Vidhan Sabha deleted successfully'})
            
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)


class PanchayatView(LoginRequiredMixin, View):
    """Panchayat management page + API endpoints"""
    template_name = 'esswebapp/pages/constituency/panchayat.html'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_panchayat_api(request)
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})
    
    def post(self, request):
        return self._create_panchayat(request)
    
    def put(self, request):
        return self._update_panchayat(request)
    
    def delete(self, request):
        return self._delete_panchayat(request)
    
    def _get_panchayat_queryset(self):
        return Panchayat.objects.filter(status=True).select_related('district', 'vidhan_sabha').order_by('-created_on')
    
    def _list_panchayat_api(self, request):
        try:
            # If id is provided, return single panchayat
            p_id = request.GET.get('id')
            if p_id:
                try:
                    p = Panchayat.objects.filter(status=True).select_related('district', 'vidhan_sabha').annotate(
                        village_count=Count('villages', filter=models.Q(villages__status=True))
                    ).get(id=p_id)
                    
                    return JsonResponse({
                        'id': p.id,
                        'panchayat_guid_id': p.panchayat_guid_id,
                        'name': p.name,
                        'status': p.status,
                        'district_id': p.district_id,
                        'district_name': p.district.name if p.district else None,
                        'vidhan_sabha_id': p.vidhan_sabha_id,
                        'vidhan_sabha_name': p.vidhan_sabha.name if p.vidhan_sabha else None,
                        'created_by': p.created_by,
                        'created_on': p.created_on.isoformat() if p.created_on else None,
                        'updated_by': p.updated_by,
                        'updated_on': p.updated_on.isoformat() if p.updated_on else None,
                        'village_count': p.village_count
                    })
                except Panchayat.DoesNotExist:
                    return JsonResponse({'detail': 'Panchayat not found'}, status=404)
            
            # Otherwise return paginated list
            queryset = self._get_panchayat_queryset()
            
            # Add village count
            queryset = queryset.annotate(
                village_count=Count('villages', filter=models.Q(villages__status=True))
            )
            
            # Filter by district if provided
            district_id = request.GET.get('district_id')
            print("district_id", district_id)
            if district_id:
                queryset = queryset.filter(district_id=district_id)
            
            # Filter by vidhan_sabha if provided
            vidhan_sabha_id = request.GET.get('vidhan_sabha_id')
            if vidhan_sabha_id:
                queryset = queryset.filter(vidhan_sabha_id=vidhan_sabha_id)
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', PAGE_SIZE))
            search = request.GET.get('search', '').strip().lower()
            
            if search:
                queryset = queryset.filter(models.Q(name__icontains=search))
            
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            items = []
            for p in queryset[start:end]:
                items.append({
                    'id': p.id,
                    'panchayat_guid_id': p.panchayat_guid_id,
                    'name': p.name,
                    'status': p.status,
                    'district_id': p.district_id,
                    'district_name': p.district.name if p.district else None,
                    'vidhan_sabha_id': p.vidhan_sabha_id,
                    'vidhan_sabha_name': p.vidhan_sabha.name if p.vidhan_sabha else None,
                    'created_by': p.created_by,
                    'created_on': p.created_on.isoformat() if p.created_on else None,
                    'updated_by': p.updated_by,
                    'updated_on': p.updated_on.isoformat() if p.updated_on else None,
                    'village_count': p.village_count
                })
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _create_panchayat(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            district_id = data.get('district_id')
            vidhan_sabha_id = data.get('vidhan_sabha_id')
            
            if not name:
                return JsonResponse({'detail': 'Panchayat name is required'}, status=400)
            if not district_id:
                return JsonResponse({'detail': 'District is required'}, status=400)
            if not vidhan_sabha_id:
                return JsonResponse({'detail': 'Vidhan Sabha is required'}, status=400)
            
            if Panchayat.objects.filter(name__iexact=name, vidhan_sabha_id=vidhan_sabha_id, status=True).exists():
                return JsonResponse({'detail': 'A Panchayat with this name already exists in this Vidhan Sabha'}, status=400)
            
            user_id = request.web_user.get('user_id')
            p_guid = str(uuid.uuid4())
            
            p = Panchayat.objects.create(
                panchayat_guid_id=p_guid,
                name=name,
                district_id=district_id,
                vidhan_sabha_id=vidhan_sabha_id,
                status=True,
                created_by=user_id,
                created_on=timezone.now(),
                updated_by=user_id,
                updated_on=timezone.now()
            )
            
            return JsonResponse({
                'id': p.id,
                'panchayat_guid_id': p.panchayat_guid_id,
                'name': p.name,
                'status': p.status,
                'district_id': p.district_id,
                'district_name': p.district.name if p.district else None,
                'vidhan_sabha_id': p.vidhan_sabha_id,
                'vidhan_sabha_name': p.vidhan_sabha.name if p.vidhan_sabha else None,
                'created_by': p.created_by,
                'created_on': p.created_on,
                'updated_by': p.updated_by,
                'updated_on': p.updated_on,
                'village_count': 0
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _update_panchayat(self, request):
        try:
            data = json.loads(request.body)
            p_id = data.get('id')
            name = data.get('name', '').strip()
            district_id = data.get('district_id')
            vidhan_sabha_id = data.get('vidhan_sabha_id')
            
            if not p_id:
                return JsonResponse({'detail': 'Panchayat ID is required'}, status=400)
            if not name:
                return JsonResponse({'detail': 'Panchayat name is required'}, status=400)
            if not district_id:
                return JsonResponse({'detail': 'District is required'}, status=400)
            if not vidhan_sabha_id:
                return JsonResponse({'detail': 'Vidhan Sabha is required'}, status=400)
            
            try:
                p = Panchayat.objects.get(id=p_id, status=True)
            except Panchayat.DoesNotExist:
                return JsonResponse({'detail': 'Panchayat not found'}, status=404)
            
            if Panchayat.objects.filter(name__iexact=name, vidhan_sabha_id=vidhan_sabha_id, status=True).exclude(id=p_id).exists():
                return JsonResponse({'detail': 'A Panchayat with this name already exists in this Vidhan Sabha'}, status=400)
            
            user_id = request.web_user.get('user_id')
            p.name = name
            p.district_id = district_id
            p.vidhan_sabha_id = vidhan_sabha_id
            p.updated_by = user_id
            p.updated_on = timezone.now()
            p.save(update_fields=['name', 'district_id', 'vidhan_sabha_id', 'updated_by', 'updated_on'])
            
            return JsonResponse({
                'id': p.id,
                'panchayat_guid_id': p.panchayat_guid_id,
                'name': p.name,
                'status': p.status,
                'district_id': p.district_id,
                'district_name': p.district.name if p.district else None,
                'vidhan_sabha_id': p.vidhan_sabha_id,
                'vidhan_sabha_name': p.vidhan_sabha.name if p.vidhan_sabha else None,
                'created_by': p.created_by,
                'created_on': p.created_on,
                'updated_by': p.updated_by,
                'updated_on': p.updated_on,
                'village_count': p.villages.filter(status=True).count()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _delete_panchayat(self, request):
        try:
            p_id = request.GET.get('id')
            if not p_id:
                try:
                    data = json.loads(request.body)
                    p_id = data.get('id')
                except:
                    pass
            
            if not p_id:
                return JsonResponse({'detail': 'Panchayat ID is required'}, status=400)
            
            try:
                p = Panchayat.objects.get(id=p_id, status=True)
            except Panchayat.DoesNotExist:
                return JsonResponse({'detail': 'Panchayat not found'}, status=404)
            
            p.status = False
            p.updated_by = request.web_user.get('user_id')
            p.updated_on = timezone.now()
            p.save(update_fields=['status', 'updated_by', 'updated_on'])
            
            return JsonResponse({'detail': 'Panchayat deleted successfully'})
            
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)


class VillageView(LoginRequiredMixin, View):
    """Village management page + API endpoints"""
    template_name = 'esswebapp/pages/constituency/village.html'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_village_api(request)
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})
    
    def post(self, request):
        return self._create_village(request)
    
    def put(self, request):
        return self._update_village(request)
    
    def delete(self, request):
        return self._delete_village(request)
    
    def _get_village_queryset(self):
        return Village.objects.filter(status=True).select_related('district', 'vidhan_sabha', 'panchayat').order_by('-created_on')
    
    def _list_village_api(self, request):
        try:
            v_id = request.GET.get('id')
            if v_id:
                try:
                    v = Village.objects.filter(status=True).select_related('district', 'vidhan_sabha', 'panchayat').get(id=v_id)
                    
                    return JsonResponse({
                        'id': v.id,
                        'village_guid_id': v.village_guid_id,
                        'name': v.name,
                        'status': v.status,
                        'district_id': v.district_id,
                        'district_name': v.district.name if v.district else None,
                        'vidhan_sabha_id': v.vidhan_sabha_id,
                        'vidhan_sabha_name': v.vidhan_sabha.name if v.vidhan_sabha else None,
                        'panchayat_id': v.panchayat_id,
                        'panchayat_name': v.panchayat.name if v.panchayat else None,
                        'created_by': v.created_by,
                        'created_on': v.created_on.isoformat() if v.created_on else None,
                        'updated_by': v.updated_by,
                        'updated_on': v.updated_on.isoformat() if v.updated_on else None
                    })
                except Village.DoesNotExist:
                    return JsonResponse({'detail': 'Village not found'}, status=404)
            
            queryset = self._get_village_queryset()
            
            # Filter by district if provided
            district_id = request.GET.get('district_id')
            if district_id:
                queryset = queryset.filter(district_id=district_id)
            
            # Filter by vidhan_sabha if provided
            vidhan_sabha_id = request.GET.get('vidhan_sabha_id')
            if vidhan_sabha_id:
                queryset = queryset.filter(vidhan_sabha_id=vidhan_sabha_id)
            
            # Filter by panchayat if provided
            panchayat_id = request.GET.get('panchayat_id')
            if panchayat_id:
                queryset = queryset.filter(panchayat_id=panchayat_id)
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', PAGE_SIZE))
            search = request.GET.get('search', '').strip().lower()
            
            if search:
                queryset = queryset.filter(models.Q(name__icontains=search))
            
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            items = []
            for v in queryset[start:end]:
                items.append({
                    'id': v.id,
                    'village_guid_id': v.village_guid_id,
                    'name': v.name,
                    'status': v.status,
                    'district_id': v.district_id,
                    'district_name': v.district.name if v.district else None,
                    'vidhan_sabha_id': v.vidhan_sabha_id,
                    'vidhan_sabha_name': v.vidhan_sabha.name if v.vidhan_sabha else None,
                    'panchayat_id': v.panchayat_id,
                    'panchayat_name': v.panchayat.name if v.panchayat else None,
                    'created_by': v.created_by,
                    'created_on': v.created_on.isoformat() if v.created_on else None,
                    'updated_by': v.updated_by,
                    'updated_on': v.updated_on.isoformat() if v.updated_on else None
                })
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _create_village(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            district_id = data.get('district_id')
            vidhan_sabha_id = data.get('vidhan_sabha_id')
            panchayat_id = data.get('panchayat_id')
            
            if not name:
                return JsonResponse({'detail': 'Village name is required'}, status=400)
            if not district_id:
                return JsonResponse({'detail': 'District is required'}, status=400)
            if not vidhan_sabha_id:
                return JsonResponse({'detail': 'Vidhan Sabha is required'}, status=400)
            if not panchayat_id:
                return JsonResponse({'detail': 'Panchayat is required'}, status=400)
            
            if Village.objects.filter(name__iexact=name, panchayat_id=panchayat_id, status=True).exists():
                return JsonResponse({'detail': 'A Village with this name already exists in this Panchayat'}, status=400)
            
            user_id = request.web_user.get('user_id')
            v_guid = str(uuid.uuid4())
            
            v = Village.objects.create(
                village_guid_id=v_guid,
                name=name,
                district_id=district_id,
                vidhan_sabha_id=vidhan_sabha_id,
                panchayat_id=panchayat_id,
                status=True,
                created_by=user_id,
                created_on=timezone.now(),
            )
            
            return JsonResponse({
                'id': v.id,
                'village_guid_id': v.village_guid_id,
                'name': v.name,
                'status': v.status,
                'district_id': v.district_id,
                'district_name': v.district.name if v.district else None,
                'vidhan_sabha_id': v.vidhan_sabha_id,
                'vidhan_sabha_name': v.vidhan_sabha.name if v.vidhan_sabha else None,
                'panchayat_id': v.panchayat_id,
                'panchayat_name': v.panchayat.name if v.panchayat else None,
                'created_by': v.created_by,
                'created_on': v.created_on,
                'updated_by': v.updated_by,
                'updated_on': v.updated_on
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _update_village(self, request):
        try:
            data = json.loads(request.body)
            v_id = data.get('id')
            name = data.get('name', '').strip()
            district_id = data.get('district_id')
            vidhan_sabha_id = data.get('vidhan_sabha_id')
            panchayat_id = data.get('panchayat_id')
            
            if not v_id:
                return JsonResponse({'detail': 'Village ID is required'}, status=400)
            if not name:
                return JsonResponse({'detail': 'Village name is required'}, status=400)
            if not district_id:
                return JsonResponse({'detail': 'District is required'}, status=400)
            if not vidhan_sabha_id:
                return JsonResponse({'detail': 'Vidhan Sabha is required'}, status=400)
            if not panchayat_id:
                return JsonResponse({'detail': 'Panchayat is required'}, status=400)
            
            try:
                v = Village.objects.get(id=v_id, status=True)
            except Village.DoesNotExist:
                return JsonResponse({'detail': 'Village not found'}, status=404)
            
            if Village.objects.filter(name__iexact=name, panchayat_id=panchayat_id, status=True).exclude(id=v_id).exists():
                return JsonResponse({'detail': 'A Village with this name already exists in this Panchayat'}, status=400)
            
            user_id = request.web_user.get('user_id')
            v.name = name
            v.district_id = district_id
            v.vidhan_sabha_id = vidhan_sabha_id
            v.panchayat_id = panchayat_id
            v.updated_by = user_id
            v.updated_on = timezone.now()
            v.save(update_fields=['name', 'district_id', 'vidhan_sabha_id', 'panchayat_id', 'updated_by', 'updated_on'])
            
            return JsonResponse({
                'id': v.id,
                'village_guid_id': v.village_guid_id,
                'name': v.name,
                'status': v.status,
                'district_id': v.district_id,
                'district_name': v.district.name if v.district else None,
                'vidhan_sabha_id': v.vidhan_sabha_id,
                'vidhan_sabha_name': v.vidhan_sabha.name if v.vidhan_sabha else None,
                'panchayat_id': v.panchayat_id,
                'panchayat_name': v.panchayat.name if v.panchayat else None,
                'created_by': v.created_by,
                'created_on': v.created_on,
                'updated_by': v.updated_by,
                'updated_on': v.updated_on
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _delete_village(self, request):
        try:
            v_id = request.GET.get('id')
            if not v_id:
                try:
                    data = json.loads(request.body)
                    v_id = data.get('id')
                except:
                    pass
            
            if not v_id:
                return JsonResponse({'detail': 'Village ID is required'}, status=400)
            
            try:
                v = Village.objects.get(id=v_id, status=True)
            except Village.DoesNotExist:
                return JsonResponse({'detail': 'Village not found'}, status=404)
            
            v.status = False
            v.updated_by = request.web_user.get('user_id')
            v.updated_on = timezone.now()
            v.save(update_fields=['status', 'updated_by', 'updated_on'])
            
            return JsonResponse({'detail': 'Village deleted successfully'})
            
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)