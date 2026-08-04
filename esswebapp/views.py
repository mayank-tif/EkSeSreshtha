from django.core.files.storage import default_storage
from django.shortcuts import render, redirect
from django.views import View
from django.urls import re_path
from django.utils import timezone
from django.http import JsonResponse
from django.db import models
from django.db.models import Count
import json
import uuid
import logging
from datetime import datetime

from APIS.models import *
from APIS.utils import hash_password
from .helpers import save_center_web
from .forms import LoginForm
import base64
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


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
                'error': 'User does not exists!'
            })
        
        # Check password using same hashing as APIS app
        print("user.password", user.password, hash_password(password))
        if hash_password(password) != user.password:
            return render(request, self.template_name, {
                'form': form,
                'error': 'Incorrect password!'
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


class SchoolDropDownView(LoginRequiredMixin, View):
    """API view for listing schools - used in dropdowns"""
    
    def get(self, request):
        try:
            
            queryset = School.objects.filter(status=True).order_by('school_name')
            
            schools_page = list(queryset.values('id', 'school_name'))
            
            items = [
                {'id': s['id'], 'name': s['school_name']}
                for s in schools_page
            ]
            
            return JsonResponse({
                'results': items,
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)


class SchoolListView(LoginRequiredMixin, View):
    """School management page + API endpoints"""
    template_name = 'esswebapp/pages/students/school-list.html'
    
    def get(self, request):
        # Check if it's an AJAX request for JSON data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_schools_api(request)
        
        # Render the HTML page
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})
    
    def post(self, request):
        # Create new school
        return self._create_school(request)
    
    def put(self, request):
        # Update existing school
        return self._update_school(request)
    
    def delete(self, request):
        # Soft delete (set status=0)
        return self._delete_school(request)
    
    def _list_schools_api(self, request):
        """Return paginated schools as JSON for table, or single school if id provided"""
        try:
            
            # If id is provided, return single school
            school_id = request.GET.get('id')
            if school_id:
                try:
                    school = School.objects.filter(status=True).get(id=school_id)
                    return JsonResponse({
                        'id': school.id,
                        'schoolName': school.school_name,
                        'status': school.status,
                        'created_by': school.created_by,
                        'created_on': school.created_on.isoformat() if school.created_on else None,
                        'updated_by': school.updated_by,
                        'updated_on': school.updated_on.isoformat() if school.updated_on else None,
                    })
                except School.DoesNotExist:
                    return JsonResponse({'detail': 'School not found'}, status=404)
            
            # Otherwise return paginated list
            schools = School.objects.filter(status=True).order_by('-created_on')
            
            # Pagination params
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', PAGE_SIZE))
            search = request.GET.get('search', '').strip().lower()
            
            if search:
                schools = schools.filter(
                    models.Q(school_name__icontains=search)
                )
            
            total = schools.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            items = []
            for s in schools[start:end]:
                items.append({
                    'id': s.id,
                    'schoolName': s.school_name,
                    'status': s.status,
                    'created_by': s.created_by,
                    'created_on': s.created_on.isoformat() if s.created_on else None,
                    'updated_by': s.updated_by,
                    'updated_on': s.updated_on.isoformat() if s.updated_on else None,
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
    
    def _create_school(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            
            if not name:
                return JsonResponse({'detail': 'School name is required'}, status=400)
            
            # Check if school with same name exists
            if School.objects.filter(school_name__iexact=name, status=True).exists():
                return JsonResponse({'detail': 'A school with this name already exists'}, status=400)
            
            # Get user ID from session
            user_id = request.web_user.get('user_id')
            
            school = School.objects.create(
                school_name=name,
                status=True,
                created_by=user_id,
                created_on=timezone.now(),
            )
            
            return JsonResponse({
                'id': school.id,
                'schoolName': school.school_name,
                'status': school.status,
                'created_by': school.created_by,
                'created_on': school.created_on.isoformat() if school.created_on else None,
                'updated_by': school.updated_by,
                'updated_on': school.updated_on.isoformat() if school.updated_on else None,
            }, status=201)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _update_school(self, request):
        try:
            data = json.loads(request.body)
            school_id = data.get('id')
            name = data.get('name', '').strip()
            
            if not school_id or not name:
                return JsonResponse({'detail': 'School ID and name are required'}, status=400)
            
            school = School.objects.filter(id=school_id).first()
            if not school:
                return JsonResponse({'detail': 'School not found'}, status=404)
            
            # Check duplicate (excluding self)
            if School.objects.filter(school_name__iexact=name, status=True).exclude(id=school_id).exists():
                return JsonResponse({'detail': 'A school with this name already exists'}, status=400)
            
            # Get user ID from session
            user_id = request.web_user.get('user_id')
            
            school.school_name = name
            school.updated_by = user_id
            school.updated_on = timezone.now()
            school.save()
            
            return JsonResponse({
                'id': school.id,
                'schoolName': school.school_name,
                'status': school.status,
                'created_by': school.created_by,
                'created_on': school.created_on.isoformat() if school.created_on else None,
                'updated_by': school.updated_by,
                'updated_on': school.updated_on.isoformat() if school.updated_on else None,
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _delete_school(self, request):
        try:
            data = json.loads(request.body)
            school_id = data.get('id')
            
            if not school_id:
                return JsonResponse({'detail': 'School ID is required'}, status=400)
            
            school = School.objects.filter(id=school_id).first()
            if not school:
                return JsonResponse({'detail': 'School not found'}, status=404)
            
            # Get user ID from session
            user_id = request.web_user.get('user_id')
            
            school.status = False
            school.updated_by = user_id
            school.updated_on = timezone.now()
            school.save()
            
            return JsonResponse({'detail': 'School deleted successfully'})
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)


class ClassListView(LoginRequiredMixin, View):
    """API view for listing classes by centre - used in dropdowns"""
    
    def get(self, request):
        try:
            center_id = request.GET.get('center_id')
            if not center_id:
                return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 1000, 'total_pages': 1})
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 1000))
            
            from APIS.models import ClassModel
            queryset = ClassModel.objects.filter(
                center_id=center_id,
                active_status=True,
                status=1  # Active classes only
            ).order_by('name')
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            classes_page = list(queryset[start:end].values('id', 'name'))
            
            items = [
                {'id': c['id'], 'name': c['name']}
                for c in classes_page
            ]
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)


class StudentRegistrationView(LoginRequiredMixin, View):
    """View for student registration page"""
    template_name = 'esswebapp/pages/students/student-registration.html'
    
    def get(self, request):
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})


class StudentsView(LoginRequiredMixin, View):
    template_name = 'esswebapp/pages/students/student-list.html'
    
    def get(self, request):
        # Check if it's an AJAX request for JSON data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_students_api(request)
        
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})

    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Transform web app field names to model field names
            student_data = {
                'roll_number': int(data.get('rollNo')) if data.get('rollNo') else None,
                'enrollment_id': str(uuid.uuid4()),
                'full_name': data.get('name') or data.get('full_name'),
                'age': data.get('age'),
                'gender': data.get('gender'),
                'date_of_birth': self._parse_date(data.get('dateOfBirth')),
                'joining_date': self._parse_datetime(data.get('joiningDate')),
                'grade': data.get('grade'),
                'father_name': data.get('fatherName'),
                'mother_name': data.get('motherName'),
                'father_mobile_number': data.get('fatherMobile'),
                'mother_mobile_number': data.get('motherMobile'),
                'father_occupation': data.get('fatherOccupation'),
                'mother_occupation': data.get('motherOccupation'),
                'phone_number': data.get('contactNumber'),
                'whats_app': data.get('whatsApp'),
                'full_address': data.get('address'),
                'email': data.get('email'),
                'category': data.get('category'),
                'bpl': (lambda v: v.lower() == 'true' or v == 'Yes' or v is True if isinstance(v, str) else bool(v))(data.get('bpl')),
                'school_id': data.get('schoolId'),
                'center_id': data.get('centreId'),
                'status': True,
                'district_id': data.get('district_id'),
                'vidhan_sabha_id': data.get('vidhan_sabha_id'),
                'panchayat_id': data.get('panchayat_id'),
                'village_id': data.get('village_id'),
                'created_by': request.web_user.get('user_id'),
                'created_on': datetime.now()
            }
            
            # Remove None values for optional fields
            student_data = {k: v for k, v in student_data.items() if v is not None}
            
            # Check for duplicate roll_number per center
            roll_number = student_data.get('roll_number')
            center_id = student_data.get('center_id')
            if roll_number and center_id:
                if Student.objects.filter(roll_number=roll_number, center_id=center_id, status=True).exists():
                    return JsonResponse({'detail': 'Roll number already exists for this centre'}, status=400)
            
            # Handle profile image - decode base64 and save as file
            profile_image_data = data.get('image') or data.get('profile_image')
            if profile_image_data and isinstance(profile_image_data, str) and profile_image_data.startswith('data:image'):
                # Decode base64 and save as file
                try:
                    format, imgstr = profile_image_data.split(';base64,')
                    ext = format.split('/')[-1]
                    # Use shorter filename to fit in 50-char column
                    short_uuid = uuid.uuid4().hex[:8]
                    filename = f"p_{request.web_user.get('user_id')}_{short_uuid}.{ext}"
                    filepath = f"profile_pic/{filename}"
                    student_data['profile_image'] = default_storage.save(filepath, ContentFile(base64.b64decode(imgstr)))
                except Exception as e:
                    logger.warning(f"Failed to save profile image: {e}")
            
            # Create Student model directly
            student = Student.objects.create(**student_data)
            
            return JsonResponse({
                'status': True,
                'message': 'Student registered successfully',
                'data': self._serialize_student(student)
            }, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def put(self, request):
        try:
            data = json.loads(request.body)
            # If status is provided with only id (status toggle)
            if 'status' in data or 'Status' in data:
                if len(data) <= 2 and ('id' in data or 'Id' in data or len(data) == 1):
                    return self._toggle_student_status(request)
        except:
            pass
        return self._update_student(request)
    
    def delete(self, request):
        return self._delete_student(request)
    
    def _get_students_queryset(self):
        """Get students with related data"""
        return Student.objects.select_related(
            'center', 'school', 'district', 'vidhan_sabha', 'panchayat', 'village'
        ).order_by('-created_on')
    
    def _get_user_names_map(self, user_ids):
        """Batch-fetch user names for the given ids."""
        ids = [i for i in set(user_ids) if i]
        if not ids:
            return {}
        return dict(User.objects.filter(id__in=ids).values_list('id', 'name'))
    
    def _get_student_school_map(self, student_ids):
        """Batch-fetch school names for student ids."""
        if not student_ids:
            return {}
        schools = School.objects.filter(id__in=student_ids).values_list('id', 'school_name')
        return dict(schools)
    

    def _list_classes_api(self, request):
        """Return list of classes for dropdown selection, filtered by center_id."""
        try:
            center_id = request.GET.get('center_id')
            if not center_id:
                return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 1000, 'total_pages': 1})
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 1000))
            
            queryset = ClassModel.objects.filter(
                center_id=center_id,
                active_status=True,
                status=1  # Active classes only
            ).order_by('name')
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            classes_page = list(queryset[start:end].values('id', 'name'))
            
            items = [
                {'id': c['id'], 'name': c['name']}
                for c in classes_page
            ]
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)

    def _format_date(self, date_val):
        """Format date value to ISO format string, handling both date objects and strings."""
        if not date_val:
            return None
        if hasattr(date_val, 'isoformat'):
            return date_val.isoformat()
        # Handle string dates (DD-MM-YYYY or YYYY-MM-DD)
        if isinstance(date_val, str):
            try:
                # Try DD-MM-YYYY
                if '-' in date_val and len(date_val) == 10:
                    parts = date_val.split('-')
                    if len(parts[0]) == 2:  # DD-MM-YYYY
                        from datetime import datetime
                        return datetime.strptime(date_val, '%d-%m-%Y').date().isoformat()
                    elif len(parts[0]) == 4:  # YYYY-MM-DD
                        return date_val
            except:
                pass
        return str(date_val)
    
    def _list_students_api(self, request):
        try:
            student_id = request.GET.get('id')
            if student_id:
                try:
                    student = self._get_students_queryset().get(id=student_id)
                    # Fetch center and school names for single student
                    center_map = {}
                    school_map = {}
                    if student.center_id:
                        center = Center.objects.filter(id=student.center_id).values('id', 'center_name', 'assigned_teachers', 'assigned_regional_admin').first()
                        if center:
                            center_map[center['id']] = center['center_name']
                            # Get teacher and regional admin names
                            user_ids = []
                            if center['assigned_teachers']:
                                user_ids.append(center['assigned_teachers'])
                            if center['assigned_regional_admin']:
                                user_ids.append(center['assigned_regional_admin'])
                            name_map = self._get_user_names_map(user_ids)
                            student.center.assigned_teacher_name = name_map.get(center['assigned_teachers'])
                            student.center.assigned_regional_admin_name = name_map.get(center['assigned_regional_admin'])
                    if student.school_id:
                        school = School.objects.filter(id=student.school_id).values('id', 'school_name').first()
                        if school:
                            school_map[school['id']] = school['school_name']
                    return JsonResponse(self._serialize_student(student, center_map, school_map))
                except Student.DoesNotExist:
                    return JsonResponse({'detail': 'Student not found'}, status=404)
            
            queryset = self._get_students_queryset()
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
            search = request.GET.get('search', '').strip().lower()
            
            # Location filters
            district_id = request.GET.get('district_id')
            vidhan_sabha_id = request.GET.get('vidhan_sabha_id')
            panchayat_id = request.GET.get('panchayat_id')
            village_id = request.GET.get('village_id')
            
            if district_id:
                queryset = queryset.filter(district_id=district_id)
            if vidhan_sabha_id:
                queryset = queryset.filter(vidhan_sabha_id=vidhan_sabha_id)
            if panchayat_id:
                queryset = queryset.filter(panchayat_id=panchayat_id)
            if village_id:
                queryset = queryset.filter(village_id=village_id)
            
            if search:
                queryset = queryset.filter(
                    models.Q(full_name__icontains=search) |
                    models.Q(enrollment_id__icontains=search) |
                    models.Q(father_name__icontains=search) |
                    models.Q(phone_number__icontains=search)
                )
            
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            students_page = list(queryset[start:end])
            
            # Batch-fetch related display data
            center_ids = [s.center_id for s in students_page if s.center_id]
            school_ids = [s.school_id for s in students_page if s.school_id]
            
            centers = Center.objects.filter(id__in=center_ids).values('id', 'center_name')
            center_map = {c['id']: c['center_name'] for c in centers}
            
            schools = School.objects.filter(id__in=school_ids).values('id', 'school_name')
            school_map = {s['id']: s['school_name'] for s in schools}
            
            items = [
                self._serialize_student(s, center_map, school_map)
                for s in students_page
            ]
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _serialize_student(self, student, center_map=None, school_map=None):
        center_map = center_map or {}
        school_map = school_map or {}
        
        # Handle both Student model objects and dicts (from save_student helper)
        def get_val(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)
        
        # Get center_id
        center_id = get_val(student, 'center_id') or get_val(student, 'CenterId')
        
        # Get student's own location names (from student's direct FKs)
        district_name = None
        vidhan_sabha_name = None
        panchayat_name = None
        village_name = None
        
        # Get center's location names (from center's FKs - more reliable as they're interconnected)
        center_district_name = None
        center_vidhan_sabha_name = None
        center_panchayat_name = None
        center_village_name = None
        center_address = None
        center_latitude = None
        center_longitude = None
        center_location_status = None
        center_teacher_name = None
        center_regional_admin_name = None
        
        if not isinstance(student, dict):
            # Student's direct location FKs
            district_name = student.district.name if student.district else None
            vidhan_sabha_name = student.vidhan_sabha.name if student.vidhan_sabha else None
            panchayat_name = student.panchayat.name if student.panchayat else None
            village_name = student.village.name if student.village else None
            
            # Center's location FKs (preferred - they're interconnected: District -> VS -> Panchayat -> Village)
            if student.center:
                center_district_name = student.center.district.name if student.center.district else None
                center_vidhan_sabha_name = student.center.vidhan_sabha.name if student.center.vidhan_sabha else None
                center_panchayat_name = student.center.panchayat.name if student.center.panchayat else None
                center_village_name = student.center.village.name if student.center.village else None
                center_address = student.center.address
                center_latitude = float(student.center.latitude) if student.center.latitude else None
                center_longitude = float(student.center.longitude) if student.center.longitude else None
                center_location_status = student.center.location_status
                # Center's assigned teacher and regional admin
                center_teacher_name = student.center.assigned_teacher_name if hasattr(student.center, 'assigned_teacher_name') else None
                center_regional_admin_name = student.center.assigned_regional_admin_name if hasattr(student.center, 'assigned_regional_admin_name') else None
        
        # Handle Bpl field - DB stores '0'/'1' as strings, convert to boolean
        bpl_raw = get_val(student, 'bpl') or get_val(student, 'Bpl')
        if isinstance(bpl_raw, str):
            bpl_val = bpl_raw.lower() in ('1', 'true', 'yes')
        else:
            bpl_val = bool(bpl_raw)
        
        return {
            'id': get_val(student, 'id') or get_val(student, 'Id'),
            'enrollment_id': get_val(student, 'enrollment_id') or get_val(student, 'EnrollmentId'),
            'roll_number': get_val(student, 'roll_number') or get_val(student, 'RollNumber'),
            'full_name': get_val(student, 'full_name') or get_val(student, 'FullName'),
            'mother_name': get_val(student, 'mother_name') or get_val(student, 'MotherName'),
            'father_name': get_val(student, 'father_name') or get_val(student, 'FatherName'),
            'age': get_val(student, 'age') or get_val(student, 'Age'),
            'gender': get_val(student, 'gender') or get_val(student, 'Gender'),
            'contact': get_val(student, 'phone_number') or get_val(student, 'PhoneNumber') or get_val(student, 'Contact'),
            'date_of_birth': self._format_date(get_val(student, 'date_of_birth') or get_val(student, 'DateOfBirth')),
            'email': get_val(student, 'email') or get_val(student, 'Email'),
            'remarks': get_val(student, 'remarks') or get_val(student, 'Remarks'),
            'grade': get_val(student, 'grade') or get_val(student, 'Grade'),
            'phone_number': get_val(student, 'phone_number') or get_val(student, 'PhoneNumber'),
            'image': (lambda p: f'/media/{p}' if p and not p.startswith('http') and not p.startswith('/media/') and not p.startswith('data:') else p)(get_val(student, 'profile_image') or get_val(student, 'ProfileImage')),
            'whatsapp': get_val(student, 'whats_app') or get_val(student, 'WhatsApp'),
            'full_address': get_val(student, 'full_address') or get_val(student, 'FullAddress'),
            'status': get_val(student, 'status') or get_val(student, 'Status'),
            'joining_date': self._format_date(get_val(student, 'joining_date') or get_val(student, 'JoiningDate')),
            'center_id': center_id,
            'center_name': center_map.get(center_id) if center_id else None,
            'center_address': center_address,
            'center_latitude': center_latitude,
            'center_longitude': center_longitude,
            'center_location_status': center_location_status,
            'center_teacher_name': center_teacher_name,
            'center_regional_admin_name': center_regional_admin_name,
            'teacher_name': None,
            'district_id': get_val(student, 'district_id') or get_val(student, 'DistrictId'),
            'vidhan_sabha_id': get_val(student, 'vidhan_sabha_id') or get_val(student, 'VidhanSabhaId'),
            'village_id': get_val(student, 'village_id') or get_val(student, 'VillageId'),
            'panchayat_id': get_val(student, 'panchayat_id') or get_val(student, 'PanchayatId'),
            # Student's direct location (may be empty)
            'district_name': district_name,
            'vidhan_sabha_name': vidhan_sabha_name,
            'panchayat_name': panchayat_name,
            'village_name': village_name,
            # Center's location (preferred - interconnected hierarchy)
            'center_district_name': center_district_name,
            'center_vidhan_sabha_name': center_vidhan_sabha_name,
            'center_panchayat_name': center_panchayat_name,
            'center_village_name': center_village_name,
            'father_mobile_number': get_val(student, 'father_mobile_number') or get_val(student, 'FatherMobileNumber'),
            'father_occupation': get_val(student, 'father_occupation') or get_val(student, 'FatherOccupation'),
            'mother_mobile_number': get_val(student, 'mother_mobile_number') or get_val(student, 'MotherMobileNumber'),
            'mother_occupation': get_val(student, 'mother_occupation') or get_val(student, 'MotherOccupation'),
            'category': get_val(student, 'category') or get_val(student, 'Category'),
            'bpl': bpl_val,
            'school_id': get_val(student, 'school_id') or get_val(student, 'SchoolId'),
            'school_name': school_map.get(get_val(student, 'school_id') or get_val(student, 'SchoolId')) if (get_val(student, 'school_id') or get_val(student, 'SchoolId')) else None,
            'active_class': get_val(student, 'grade') or get_val(student, 'Grade'),
            'active': get_val(student, 'status') or get_val(student, 'Status')
        }
    
    
    def _parse_date(self, date_str):
        """Parse date string in various formats to date object."""
        if not date_str:
            return None
        if hasattr(date_str, 'date'):
            return date_str.date()
        if isinstance(date_str, str):
            # Try multiple formats
            for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d-%m-%y', '%d/%m/%y', '%Y-%m-%dT%H:%M:%S'):
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
        return None
    
    def _parse_datetime(self, date_str):
        """Parse datetime string in various formats to datetime object."""
        if not date_str:
            return None
        if hasattr(date_str, 'hour'):
            return date_str
        if isinstance(date_str, str):
            for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        return None
    
    def _update_student(self, request):
        try:
            data = json.loads(request.body)
            
            student_id = data.get('id') or data.get('Id')
            if not student_id:
                return JsonResponse({'detail': 'ID is required'}, status=400)
            
            # Get existing student
            try:
                student = Student.objects.get(id=student_id, status=True)
            except Student.DoesNotExist:
                return JsonResponse({'detail': 'Student not found'}, status=404)
            
            # Update fields if provided
            field_mapping = {
                'enrollment_id': 'rollNo',
                'roll_number': 'rollNo',
                'full_name': 'name',
                'age': 'age',
                'gender': 'gender',
                'date_of_birth': 'dateOfBirth',
                'joining_date': 'joiningDate',
                'grade': 'grade',
                'father_name': 'fatherName',
                'mother_name': 'motherName',
                'father_mobile_number': 'fatherMobile',
                'mother_mobile_number': 'motherMobile',
                'father_occupation': 'fatherOccupation',
                'mother_occupation': 'motherOccupation',
                'phone_number': 'contactNumber',
                'whats_app': 'whatsApp',
                'full_address': 'address',
                'email': 'email',
                'category': 'category',
                'bpl': 'bpl',
                'school_id': 'schoolId',
                'center_id': 'centreId',
                'profile_image': 'image',
                'district_id': 'district_id',
                'vidhan_sabha_id': 'vidhan_sabha_id',
                'panchayat_id': 'panchayat_id',
                'village_id': 'village_id',
            }
            
            # Check for duplicate roll_number per center (if roll_number is being updated)
            new_roll_number = data.get('rollNo')
            new_center_id = data.get('centreId') or student.center_id
            if new_roll_number and new_center_id and int(new_roll_number) != student.roll_number:
                if Student.objects.filter(roll_number=int(new_roll_number), center_id=new_center_id, status=True).exclude(id=student_id).exists():
                    return JsonResponse({'detail': 'Roll number already exists for this centre'}, status=400)
            
            # Handle profile image - decode base64 and save as file
            profile_image_data = data.get('image') or data.get('profile_image')
            if profile_image_data and isinstance(profile_image_data, str) and profile_image_data.startswith('data:image'):
                # Decode base64 and save as file
                try:
                    format, imgstr = profile_image_data.split(';base64,')
                    ext = format.split('/')[-1]
                    # Use shorter filename to fit in 50-char column
                    short_uuid = uuid.uuid4().hex[:8]
                    filename = f"p_{request.web_user.get('user_id')}_{short_uuid}.{ext}"
                    filepath = f"profile_pic/{filename}"
                    student.profile_image = default_storage.save(filepath, ContentFile(base64.b64decode(imgstr)))
                except Exception as e:
                    logger.warning(f"Failed to save profile image: {e}")
            
            for model_field, data_field in field_mapping.items():
                # Skip profile_image as it's handled above
                if model_field == 'profile_image':
                    continue
                if data_field in data and data[data_field] is not None:
                    value = data[data_field]
                    if model_field in ['age'] and value != '':
                        value = int(value)
                    elif model_field in ['roll_number'] and value != '':
                        value = int(value)
                    elif model_field in ['district_id', 'vidhan_sabha_id', 'panchayat_id', 'village_id', 'school_id', 'center_id'] and value != '':
                        value = int(value)
                    elif model_field == 'bpl':
                        if isinstance(value, str):
                            value = value.lower() == 'true' or value == 'Yes'
                        else:
                            value = bool(value)
                    elif model_field == 'email':
                        value = value if value else None
                    print("Updating field", model_field, "to value", value)
                    setattr(student, model_field, value)
            
            student.updated_by = request.web_user.get('user_id')
            student.updated_on = datetime.now()
            student.save()
            
            return JsonResponse({
                'status': True,
                'message': 'Student updated successfully',
                'data': self._serialize_student(student)
            })
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _toggle_student_status(self, request):
        try:
            data = json.loads(request.body)
            student_id = data.get('Id') or data.get('id')
            status = data.get('Status') or data.get('status')
            print("student_id, status", student_id, status)
            
            if not student_id:
                return JsonResponse({'detail': 'Student ID is required'}, status=400)
            if status is None:
                return JsonResponse({'detail': 'Status is required'}, status=400)
            
            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return JsonResponse({'detail': 'Student not found'}, status=404)
            
            student.status = bool(int(status))
            student.updated_by = request.web_user.get('user_id')
            student.updated_on = datetime.now()
            student.save()
            
            return JsonResponse({
                'status': True,
                'message': f'Student {"activated" if student.status else "deactivated"} successfully',
                'data': self._serialize_student(student)
            })
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)

    def _delete_student(self, request):
        try:
            # Handle both query param and body
            student_id = request.GET.get('id')
            if not student_id:
                try:
                    data = json.loads(request.body)
                    student_id = data.get('id')
                except:
                    pass
            
            if not student_id:
                return JsonResponse({'detail': 'Student ID is required'}, status=400)
            
            try:
                student = Student.objects.get(id=student_id, status=True)
            except Student.DoesNotExist:
                return JsonResponse({'detail': 'Student not found'}, status=404)
            
            student.status = False
            student.updated_by = request.web_user.get('user_id')
            student.updated_on = datetime.now()
            student.save()
            
            return JsonResponse({'detail': 'Student deactivated successfully'})
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)


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
                
       
class TeacherView(LoginRequiredMixin, View):
    """Teacher management page + API endpoints"""
    template_name = 'esswebapp/pages/users/teacher.html'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_teachers_api(request)
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})
    
    def post(self, request):
        return self._create_teacher(request)
    
    def put(self, request):
        return self._update_teacher(request)
    
    def delete(self, request):
        return self._delete_teacher(request)
    
    def _get_teachers_queryset(self):
        """Get teachers ordered by created_on desc"""
        return User.objects.filter(
            status=True, role__role_code='TEACHER'
        ).select_related('role', 'teacher').order_by('-created_on')
    
    def _list_teachers_api(self, request):
        try:
            teacher_id = request.GET.get('id')
            if teacher_id:
                try:
                    user = self._get_teachers_queryset().get(id=teacher_id)
                    
                    # Get Teacher profile
                    try:
                        teacher = Teacher.objects.select_related(
                            'district', 'vidhan_sabha', 'panchayat', 'village'
                        ).get(user=user, status=True)
                        teacher_guid = teacher.teacher_guid_id
                        teacher_district = teacher.district_id
                        teacher_district_name = teacher.district.name if teacher.district else None
                        teacher_vidhan_sabha = teacher.vidhan_sabha_id
                        teacher_vidhan_sabha_name = teacher.vidhan_sabha.name if teacher.vidhan_sabha else None
                        teacher_panchayat = teacher.panchayat_id
                        teacher_panchayat_name = teacher.panchayat.name if teacher.panchayat else None
                        teacher_village = teacher.village_id
                        teacher_village_name = teacher.village.name if teacher.village else None
                        teacher_age = teacher.age
                        teacher_gender = teacher.gender
                        teacher_dob = teacher.date_of_birth
                        teacher_contact = teacher.contact
                        teacher_full_address = teacher.full_address
                        teacher_education = teacher.education
                        teacher_guardian_name = teacher.guardian_name
                        teacher_guardian_number = teacher.guardian_number
                        teacher_enrollment = teacher.enrollment_date
                        teacher_created_by = teacher.created_by
                        teacher_created_on = teacher.created_on
                        teacher_updated_by = teacher.updated_by
                        teacher_updated_on = teacher.updated_on
                    except Teacher.DoesNotExist:
                        teacher_guid = None
                        teacher_district = None
                        teacher_district_name = None
                        teacher_vidhan_sabha = None
                        teacher_vidhan_sabha_name = None
                        teacher_panchayat = None
                        teacher_panchayat_name = None
                        teacher_village = None
                        teacher_village_name = None
                        teacher_age = None
                        teacher_gender = None
                        teacher_dob = None
                        teacher_contact = None
                        teacher_full_address = None
                        teacher_education = None
                        teacher_guardian_name = None
                        teacher_guardian_number = None
                        teacher_enrollment = None
                        teacher_created_by = user.created_by
                        teacher_created_on = user.created_on
                        teacher_updated_by = user.updated_by
                        teacher_updated_on = user.updated_on
                    
                    return JsonResponse({
                        'id': user.id,
                        'teacher_guid_id': teacher_guid,
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
                        'district_id': teacher_district,
                        'district_name': teacher_district_name,
                        'vidhan_sabha_id': teacher_vidhan_sabha,
                        'vidhan_sabha_name': teacher_vidhan_sabha_name,
                        'panchayat_id': teacher_panchayat,
                        'panchayat_name': teacher_panchayat_name,
                        'village_id': teacher_village,
                        'village_name': teacher_village_name,
                        'age': teacher_age,
                        'gender': teacher_gender,
                        'date_of_birth': teacher_dob,
                        'contact': teacher_contact,
                        'full_address': teacher_full_address,
                        'education': teacher_education,
                        'guardian_name': teacher_guardian_name,
                        'guardian_number': teacher_guardian_number,
                        'enrollment_date': teacher_enrollment,
                        'created_by': teacher_created_by,
                        'created_on': teacher_created_on.isoformat() if teacher_created_on else None,
                        'updated_by': teacher_updated_by,
                        'updated_on': teacher_updated_on.isoformat() if teacher_updated_on else None
                    })
                except User.DoesNotExist:
                    return JsonResponse({'detail': 'Teacher not found'}, status=404)
            
            queryset = self._get_teachers_queryset()
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', PAGE_SIZE))
            search = request.GET.get('search', '').strip().lower()
            
            if search:
                queryset = queryset.filter(
                    models.Q(name__icontains=search) |
                    models.Q(email__icontains=search) |
                    models.Q(phone_number__icontains=search) |
                    models.Q(enrolment_roll_id__icontains=search)
                )
            
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            items = []
            for user in queryset[start:end]:
                # Get teacher profile
                try:
                    teacher = Teacher.objects.select_related(
                        'district', 'vidhan_sabha', 'panchayat', 'village'
                    ).get(user=user, status=True)
                    district_name = teacher.district.name if teacher.district else None
                    vidhan_sabha_name = teacher.vidhan_sabha.name if teacher.vidhan_sabha else None
                    panchayat_name = teacher.panchayat.name if teacher.panchayat else None
                    village_name = teacher.village.name if teacher.village else None
                except Teacher.DoesNotExist:
                    district_name = None
                    vidhan_sabha_name = None
                    panchayat_name = None
                    village_name = None
                
                items.append({
                    'id': user.id,
                    'teacher_guid_id': teacher.teacher_guid_id if hasattr(user, 'teacher') else None,
                    'user_id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'whats_app': user.whats_app,
                    'picture': user.picture.url if user.picture else None,
                    'status': user.status,
                    'enrolment_roll_id': user.enrolment_roll_id,
                    'role_code': user.role.role_code if user.role else None,
                    'district_id': teacher.district_id if hasattr(user, 'teacher') else None,
                    'district_name': district_name,
                    'vidhan_sabha_id': teacher.vidhan_sabha_id if hasattr(user, 'teacher') else None,
                    'vidhan_sabha_name': vidhan_sabha_name,
                    'panchayat_id': teacher.panchayat_id if hasattr(user, 'teacher') else None,
                    'panchayat_name': panchayat_name,
                    'village_id': teacher.village_id if hasattr(user, 'teacher') else None,
                    'village_name': village_name,
                    'age': teacher.age if hasattr(user, 'teacher') else None,
                    'gender': teacher.gender if hasattr(user, 'teacher') else None,
                    'date_of_birth': teacher.date_of_birth if hasattr(user, 'teacher') else None,
                    'contact': teacher.contact if hasattr(user, 'teacher') else None,
                    'full_address': teacher.full_address if hasattr(user, 'teacher') else None,
                    'education': teacher.education if hasattr(user, 'teacher') else None,
                    'guardian_name': teacher.guardian_name if hasattr(user, 'teacher') else None,
                    'guardian_number': teacher.guardian_number if hasattr(user, 'teacher') else None,
                    'enrollment_date': teacher.enrollment_date.isoformat() if hasattr(user, 'teacher') and teacher.enrollment_date else None,
                    'created_on': user.created_on.isoformat() if user.created_on else None,
                    'updated_on': user.updated_on.isoformat() if user.updated_on else None
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
    
    def _create_teacher(self, request):
        try:
            data = json.loads(request.body)
            
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
            full_address = data.get('full_address', '').strip()
            education = data.get('education', '').strip()
            guardian_name = data.get('guardian_name', '').strip()
            guardian_number = data.get('guardian_number', '').strip()
            enrollment_date = data.get('enrollment_date', '').strip()
            contact = data.get('contact', '').strip()
            
            if not name:
                return JsonResponse({'detail': 'Name is required'}, status=400)
            if not email:
                return JsonResponse({'detail': 'Email is required'}, status=400)
            if not password:
                return JsonResponse({'detail': 'Password is required'}, status=400)
            if not phone:
                return JsonResponse({'detail': 'Phone number is required'}, status=400)
            if not district_id:
                return JsonResponse({'detail': 'District is required'}, status=400)
            if not vidhan_sabha_id:
                return JsonResponse({'detail': 'Vidhan Sabha is required'}, status=400)
            if not panchayat_id:
                return JsonResponse({'detail': 'Panchayat is required'}, status=400)
            if not village_id:
                return JsonResponse({'detail': 'Village is required'}, status=400)
            
            if User.objects.filter(email=email).exists():
                return JsonResponse({'detail': 'Email already exists'}, status=400)
            if User.objects.filter(phone_number=phone).exists():
                return JsonResponse({'detail': 'Phone number already exists'}, status=400)
            if enrolment_roll_id and User.objects.filter(enrolment_roll_id=enrolment_roll_id).exists():
                return JsonResponse({'detail': 'Enrolment roll ID already exists'}, status=400)
            
            # Get TEACHER role
            teacher_role = Role.objects.filter(role_code='TEACHER', status=True).first()
            if not teacher_role:
                return JsonResponse({'detail': 'TEACHER role not configured'}, status=500)
            
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
                role=teacher_role,
                status=True,
                created_by=request.web_user.get('user_id'),
                created_on=timezone.now()
            )
            
            # Save picture if provided
            if picture_file:
                user.picture.save(picture_file.name, picture_file, save=True)
            
            # Create Teacher profile
            teacher = Teacher.objects.create(
                teacher_guid_id=str(uuid.uuid4()),
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

            # Parse enrollment_date if provided
            if enrollment_date:
                try:
                    teacher.enrollment_date = datetime.strptime(enrollment_date, '%Y-%m-%d').date()
                    teacher.save(update_fields=['enrollment_date'])
                except ValueError:
                    try:
                        teacher.enrollment_date = datetime.fromisoformat(enrollment_date.replace('Z', '+00:00')).date()
                        teacher.save(update_fields=['enrollment_date'])
                    except ValueError:
                        pass
            
            return JsonResponse({
                'id': user.id,
                'teacher_guid_id': teacher.teacher_guid_id,
                'user_id': user.id,
                'name': user.name,
                'email': user.email,
                'phone_number': user.phone_number,
                'whats_app': user.whats_app,
                'picture': user.picture.url if user.picture else None,
                'status': user.status,
                'enrolment_roll_id': user.enrolment_roll_id,
                'role_code': user.role.role_code,
                'district_id': teacher.district_id,
                'vidhan_sabha_id': teacher.vidhan_sabha_id,
                'panchayat_id': teacher.panchayat_id,
                'village_id': teacher.village_id,
                'message': 'Teacher created successfully'
            }, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _update_teacher(self, request):
        try:
            data = json.loads(request.body)
            user_id = data.get('id')
            
            if not user_id:
                return JsonResponse({'detail': 'ID is required'}, status=400)
            
            try:
                user = User.objects.get(id=user_id, role__role_code='TEACHER', status=True)
                teacher = Teacher.objects.get(user=user, status=True)
            except (User.DoesNotExist, Teacher.DoesNotExist):
                return JsonResponse({'detail': 'Teacher not found'}, status=404)
            
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
            enrollment_date = data.get('enrollment_date', '').strip()
            password = data.get('password', '').strip()
            
            if name:
                user.name = name
            if email and email != user.email:
                if User.objects.filter(email=email).exclude(id=user_id).exists():
                    return JsonResponse({'detail': 'Email already exists'}, status=400)
                user.email = email
            if phone and phone != user.phone_number:
                if User.objects.filter(phone_number=phone).exclude(id=user_id).exists():
                    return JsonResponse({'detail': 'Phone number already exists'}, status=400)
                user.phone_number = phone
            if whats_app is not None:
                user.whats_app = whats_app if whats_app else None
            if enrolment_roll_id is not None:
                if enrolment_roll_id and User.objects.filter(enrolment_roll_id=enrolment_roll_id).exclude(id=user_id).exists():
                    return JsonResponse({'detail': 'Enrolment roll ID already exists'}, status=400)
                user.enrolment_roll_id = enrolment_roll_id if enrolment_roll_id else None
            
            # Update password if provided
            if password:
                user.password = hash_password(password)
            
            user.updated_by = request.web_user.get('user_id')
            user.updated_on = timezone.now()
            user.save()
            
            # Handle picture (base64 data URL)
            picture_data = data.get('picture', '').strip()
            if picture_data and picture_data.startswith('data:'):
                format, imgstr = picture_data.split(';base64,')
                ext = format.split('/')[-1]
                picture_file = ContentFile(base64.b64decode(imgstr), name=f'profile_{uuid.uuid4().hex[:8]}.{ext}')
                user.picture.save(picture_file.name, picture_file, save=True)
            
            # Update teacher profile
            if district_id is not None:
                teacher.district_id = district_id if district_id else None
            if vidhan_sabha_id is not None:
                teacher.vidhan_sabha_id = vidhan_sabha_id if vidhan_sabha_id else None
            if panchayat_id is not None:
                teacher.panchayat_id = panchayat_id if panchayat_id else None
            if village_id is not None:
                teacher.village_id = village_id if village_id else None
            if age is not None:
                teacher.age = age if age else None
            if gender is not None:
                teacher.gender = gender if gender else None
            if date_of_birth is not None:
                teacher.date_of_birth = date_of_birth if date_of_birth else None
            if contact is not None:
                teacher.contact = contact if contact else None
            if full_address is not None:
                teacher.full_address = full_address if full_address else None
            if education is not None:
                teacher.education = education if education else None
            if guardian_name is not None:
                teacher.guardian_name = guardian_name if guardian_name else None
            if guardian_number is not None:
                teacher.guardian_number = guardian_number if guardian_number else None
            if enrollment_date is not None:
                if enrollment_date:
                    try:
                        teacher.enrollment_date = datetime.strptime(enrollment_date, '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            teacher.enrollment_date = datetime.fromisoformat(enrollment_date.replace('Z', '+00:00')).date()
                        except ValueError:
                            pass
                else:
                    teacher.enrollment_date = None
            
            teacher.updated_by = request.web_user.get('user_id')
            teacher.updated_on = timezone.now()
            teacher.save()
            
            return JsonResponse({
                'id': user.id,
                'teacher_guid_id': teacher.teacher_guid_id,
                'user_id': user.id,
                'name': user.name,
                'email': user.email,
                'phone_number': user.phone_number,
                'whats_app': user.whats_app,
                'picture': user.picture.url if user.picture else None,
                'status': user.status,
                'enrolment_roll_id': user.enrolment_roll_id,
                'role_code': user.role.role_code,
                'district_id': teacher.district_id,
                'vidhan_sabha_id': teacher.vidhan_sabha_id,
                'panchayat_id': teacher.panchayat_id,
                'village_id': teacher.village_id,
                'message': 'Teacher updated successfully'
            })
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _delete_teacher(self, request):
        try:
            teacher_id = request.GET.get('id')
            if not teacher_id:
                try:
                    data = json.loads(request.body)
                    teacher_id = data.get('id')
                except:
                    pass
            
            if not teacher_id:
                return JsonResponse({'detail': 'Teacher ID is required'}, status=400)
            
            try:
                user = User.objects.get(id=teacher_id, role__role_code='TEACHER', status=True)
                teacher = Teacher.objects.get(user=user, status=True)
            except (User.DoesNotExist, Teacher.DoesNotExist):
                return JsonResponse({'detail': 'Teacher not found'}, status=404)
            
            user.status = False
            user.updated_by = request.web_user.get('user_id')
            user.updated_on = timezone.now()
            user.save(update_fields=['status', 'updated_by', 'updated_on'])
            
            teacher.status = False
            teacher.updated_by = request.web_user.get('user_id')
            teacher.updated_on = timezone.now()
            teacher.save(update_fields=['status', 'updated_by', 'updated_on'])
            
            return JsonResponse({'detail': 'Teacher deactivated successfully'})
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)


class CenterView(LoginRequiredMixin, View):
    """Educational Center management page + API endpoints"""
    template_name = 'esswebapp/pages/centres/educational-centre.html'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._list_centers_api(request)
        return render(request, self.template_name, {'user': get_user_json(request.web_user)})
    
    def post(self, request):
        return self._create_center(request)
    
    def put(self, request):
        return self._update_center(request)
    
    def delete(self, request):
        return self._delete_center(request)
    
    def _get_centers_queryset(self):
        """Get centers ordered by created_on desc"""
        return Center.objects.filter(
            status=True
        ).select_related('district', 'vidhan_sabha', 'panchayat', 'village').order_by('-created_on')
    
    def _get_user_names_map(self, user_ids):
        """Batch-fetch user names for the given ids (RA / teacher display)."""
        ids = [i for i in set(user_ids) if i]
        if not ids:
            return {}
        return dict(User.objects.filter(id__in=ids).values_list('id', 'name'))
    
    def _get_student_counts_map(self, center_ids):
        """Batch-count active students per center."""
        if not center_ids:
            return {}
        return dict(
            Student.objects.filter(center_id__in=center_ids, status=True)
            .values('center_id').annotate(cnt=Count('id'))
            .values_list('center_id', 'cnt')
        )
    
    def _list_centers_api(self, request):
        try:
            center_id = request.GET.get('id')
            if center_id:
                try:
                    center = self._get_centers_queryset().get(id=center_id)
                    name_map = self._get_user_names_map([
                        center.assigned_regional_admin, center.assigned_teachers
                    ])
                    student_counts = self._get_student_counts_map([center.id])
                    return JsonResponse(self._serialize_center(center, name_map, student_counts))
                except Center.DoesNotExist:
                    return JsonResponse({'detail': 'Center not found'}, status=404)
            
            queryset = self._get_centers_queryset()
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', PAGE_SIZE))
            search = request.GET.get('search', '').strip().lower()
            
            if search:
                queryset = queryset.filter(
                    models.Q(center_name__icontains=search) |
                    models.Q(address__icontains=search) |
                    models.Q(district__name__icontains=search) |
                    models.Q(village__name__icontains=search)
                )
            
            total = queryset.count()
            total_pages = (total + page_size - 1) // page_size
            
            start = (page - 1) * page_size
            end = start + page_size
            
            centers_page = list(queryset[start:end])
            
            # Batch-fetch related display data (avoids N+1 queries)
            user_ids = []
            for c in centers_page:
                if c.assigned_regional_admin:
                    user_ids.append(c.assigned_regional_admin)
                if c.assigned_teachers:
                    user_ids.append(c.assigned_teachers)
            name_map = self._get_user_names_map(user_ids)
            student_counts = self._get_student_counts_map([c.id for c in centers_page])
            
            items = [
                self._serialize_center(c, name_map, student_counts)
                for c in centers_page
            ]
            
            return JsonResponse({
                'results': items,
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            })
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _serialize_center(self, center, name_map=None, student_counts=None):
        name_map = name_map or {}
        student_counts = student_counts or {}
        return {
            'id': center.id,
            'center_guid_id': center.center_guid_id,
            'center_name': center.center_name,
            'address': center.address,
            'latitude': float(center.latitude) if center.latitude else None,
            'longitude': float(center.longitude) if center.longitude else None,
            'location_status': center.location_status,
            'assigned_teachers': center.assigned_teachers,
            'assigned_teacher_name': name_map.get(center.assigned_teachers),
            'assigned_regional_admin': center.assigned_regional_admin,
            'assigned_regional_admin_name': name_map.get(center.assigned_regional_admin),
            'student_count': student_counts.get(center.id, 0),
            'class_status': center.class_status,
            'district_id': center.district_id,
            'district_name': center.district.name if center.district else None,
            'vidhan_sabha_id': center.vidhan_sabha_id,
            'vidhan_sabha_name': center.vidhan_sabha.name if center.vidhan_sabha else None,
            'panchayat_id': center.panchayat_id,
            'panchayat_name': center.panchayat.name if center.panchayat else None,
            'village_id': center.village_id,
            'village_name': center.village.name if center.village else None,
            'created_by': center.created_by,
            'created_on': center.created_on.isoformat() if center.created_on else None,
            'updated_by': center.updated_by,
            'updated_on': center.updated_on.isoformat() if center.updated_on else None,
            'started_date': center.started_date.isoformat() if center.started_date else None,
        }
    
    def _create_center(self, request):
        try:
            data = json.loads(request.body)
            
            center_name = data.get('center_name', '').strip()
            address = data.get('address', '').strip()
            district_id = data.get('district_id')
            vidhan_sabha_id = data.get('vidhan_sabha_id')
            panchayat_id = data.get('panchayat_id')
            village_id = data.get('village_id')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            assigned_teachers = data.get('assigned_teachers', 0)
            assigned_regional_admin = data.get('assigned_regional_admin')
            class_status = data.get('class_status', True)
            started_date = data.get('started_date')
            
            # Parse started_date if provided
            if started_date:
                try:
                    started_date = datetime.strptime(started_date, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        started_date = datetime.fromisoformat(started_date.replace('Z', '+00:00')).date()
                    except ValueError:
                        started_date = None
            
            if not center_name:
                return JsonResponse({'detail': 'Center name is required'}, status=400)
            if not address:
                return JsonResponse({'detail': 'Address is required'}, status=400)
            if not district_id:
                return JsonResponse({'detail': 'District is required'}, status=400)
            if not vidhan_sabha_id:
                return JsonResponse({'detail': 'Vidhan Sabha is required'}, status=400)
            if not panchayat_id:
                return JsonResponse({'detail': 'Panchayat is required'}, status=400)
            if not village_id:
                return JsonResponse({'detail': 'Village is required'}, status=400)
            
            # Transform data to PascalCase format expected by the web center helper
            center_data = {
                'CenterName': center_name,
                'Address': address,
                'DistrictId': district_id,
                'VidhanSabhaId': vidhan_sabha_id,
                'PanchayatId': panchayat_id,
                'VillageId': village_id,
                'Latitude': latitude,
                'Longitude': longitude,
                'AssignedTeachers': assigned_teachers if assigned_teachers else 0,
                'AssignedRegionalAdmin': assigned_regional_admin,
                'StartedDate': started_date,
                'ClassStatus': class_status
            }
            
            # Call web-app-specific save helper (Id=0 means create new)
            center_data['Id'] = 0
            center = save_center_web(center_data, request)
            
            if not center:
                return JsonResponse({'detail': 'Failed to create center'}, status=500)
            
            name_map = self._get_user_names_map([
                center.assigned_regional_admin, center.assigned_teachers
            ])
            student_counts = self._get_student_counts_map([center.id])
            response_data = self._serialize_center(center, name_map, student_counts)
            response_data['message'] = 'Center created successfully'
            return JsonResponse(response_data, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Create center error: {str(e)}")
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _update_center(self, request):
        try:
            data = json.loads(request.body)
            center_id = data.get('id')
            
            if not center_id:
                return JsonResponse({'detail': 'ID is required'}, status=400)
            
            # Transform data to PascalCase format expected by save_center helper
            center_data = {'Id': center_id}
            
            # Only include fields that are provided
            if 'center_name' in data and data['center_name'] is not None:
                center_data['CenterName'] = data['center_name'].strip()
            if 'address' in data and data['address'] is not None:
                center_data['Address'] = data['address'].strip()
            if 'district_id' in data and data['district_id'] is not None:
                center_data['DistrictId'] = data['district_id']
            if 'vidhan_sabha_id' in data and data['vidhan_sabha_id'] is not None:
                center_data['VidhanSabhaId'] = data['vidhan_sabha_id']
            if 'panchayat_id' in data and data['panchayat_id'] is not None:
                center_data['PanchayatId'] = data['panchayat_id']
            if 'village_id' in data and data['village_id'] is not None:
                center_data['VillageId'] = data['village_id']
            if 'latitude' in data and data['latitude'] is not None:
                center_data['Latitude'] = data['latitude']
            if 'longitude' in data and data['longitude'] is not None:
                center_data['Longitude'] = data['longitude']
            if 'assigned_teachers' in data and data['assigned_teachers'] is not None:
                center_data['AssignedTeachers'] = data['assigned_teachers']
            if 'assigned_regional_admin' in data and data['assigned_regional_admin'] is not None:
                center_data['AssignedRegionalAdmin'] = data['assigned_regional_admin']
            if 'started_date' in data and data['started_date'] is not None:
                started_date = data['started_date']
                if isinstance(started_date, str):
                    try:
                        started_date = datetime.strptime(started_date, '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            started_date = datetime.fromisoformat(started_date.replace('Z', '+00:00')).date()
                        except ValueError:
                            started_date = None
                center_data['StartedDate'] = started_date
            if 'class_status' in data and data['class_status'] is not None:
                center_data['ClassStatus'] = data['class_status']
            
            # Call web-app-specific save helper
            center = save_center_web(center_data, request)
            
            if not center:
                return JsonResponse({'detail': 'Center not found or failed to update'}, status=404)
            
            name_map = self._get_user_names_map([
                center.assigned_regional_admin, center.assigned_teachers
            ])
            student_counts = self._get_student_counts_map([center.id])
            response_data = self._serialize_center(center, name_map, student_counts)
            response_data['message'] = 'Center updated successfully'
            return JsonResponse(response_data, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Update center error: {str(e)}")
            return JsonResponse({'detail': str(e)}, status=500)
    
    def _delete_center(self, request):
        try:
            center_id = request.GET.get('id')
            if not center_id:
                try:
                    data = json.loads(request.body)
                    center_id = data.get('id')
                except:
                    pass
            
            if not center_id:
                return JsonResponse({'detail': 'Center ID is required'}, status=400)
            
            try:
                center = Center.objects.get(id=center_id, status=True)
            except Center.DoesNotExist:
                return JsonResponse({'detail': 'Center not found'}, status=404)
            
            center.status = False
            center.updated_by = request.web_user.get('user_id')
            center.updated_on = timezone.now()
            center.save(update_fields=['status', 'updated_by', 'updated_on'])
            
            return JsonResponse({'detail': 'Center deactivated successfully'})
        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=500)