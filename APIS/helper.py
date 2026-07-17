import json
import logging
from datetime import datetime
import uuid
from django.db.models import OuterRef, Subquery, Count
from .models import *
from django.db import IntegrityError, connection, transaction
from .utils import *
from rest_framework_simplejwt.tokens import AccessToken
from datetime import timedelta
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .utils import *


logger = logging.getLogger(__name__)

# Constants
CLASS_STATUS_ACTIVE = 1
CLASS_STATUS_COMPLETED = 2
CLASS_STATUS_CANCEL = 3


def save_profile_image(image_file, user_id):
    """Save profile image and return the relative path for ImageField"""
    if not image_file:
        return None
    
    try:
        # Generate unique filename
        ext = os.path.splitext(image_file.name)[1]
        filename = f"profile_{user_id}_{uuid.uuid4()}{ext}"
        filepath = f"profile_pic/{filename}"
        
        # Save file
        saved_path = default_storage.save(filepath, ContentFile(image_file.read()))
        
        # Return the relative path (not URL) for ImageField
        return saved_path
    except Exception as e:
        logger.error(f"Error saving profile image: {str(e)}")
        return None


def get_user_type(user_id):
    """Get user type by user ID"""
    try:
        user = User.objects.get(id=user_id)
        return user.role_id  
    except User.DoesNotExist:
        logger.error(f"User not found with ID: {user_id}")
        return None

def build_center_data(center):
    """Build center data dictionary"""
    # Get teacher name
    teacher_name = None
    if center.assigned_teachers:
        try:
            teacher = User.objects.get(id=center.assigned_teachers)
            teacher_name = teacher.name
        except User.DoesNotExist:
            teacher_name = None
    
    # Get regional admin name
    regional_admin_name = None
    if center.assigned_regional_admin:
        try:
            regional_admin = User.objects.get(id=center.assigned_regional_admin)
            regional_admin_name = regional_admin.name
        except User.DoesNotExist:
            regional_admin_name = None
    
    # Get village name
    village_name = None
    if center.village_id:
        try:
            village = Village.objects.get(id=center.village_id)
            village_name = village.name
        except Village.DoesNotExist:
            village_name = None
    
    # Get total students count
    total_students = Student.objects.filter(
        center_id=center.id,
        status=True
    ).count()
    
    return {
        'id': center.id,
        'center_name': center.center_name,
        'date': center.created_date.strftime('%Y-%m-%d %H:%M:%S') if center.created_date else None,
        'class_start_date': None,
        'class_end_date': None,
        'class_status': center.class_status,
        'status': center.status,
        'district_name': center.district.name if center.district else None,
        'vidhan_sabha_name': center.vidhan_sabha.name if center.vidhan_sabha else None,
        'village_name': village_name,
        'total_present_students': None,
        'total_students': total_students,
        'panchayat_name': center.panchayat.name if center.panchayat else None,
        'vidhan_sabha_id': center.vidhan_sabha_id,
        'district_id': center.district_id,
        'panchayat_id': center.panchayat_id,
        'assigned_teacher': center.assigned_teachers,
        'teacher_name': teacher_name,
        'assigned_regional_admin': center.assigned_regional_admin,
        'regional_admin_name': regional_admin_name,
    }

def get_centers_for_admin(status_param, today):
    """Get centers for admin user (Type == 1)"""
    all_centers = []
    
    print(f"Fetching centers for admin with status_param: {status_param} and today: {today}")
    
    if status_param == CLASS_STATUS_ACTIVE or status_param == CLASS_STATUS_COMPLETED:
        # Active or Completed classes
        classes = ClassModel.objects.filter(
            started_date__date=today,
            status=status_param
        ).select_related('center')
        
        center_ids = [cls.center_id for cls in classes if cls.center_id]
        
        centers = Center.objects.filter(
            id__in=center_ids
        ).select_related('district', 'vidhan_sabha', 'panchayat', 'village')
        
        for item in centers:
            center_data = build_center_data(item)
            
            # Get class data for this center
            class_obj = classes.filter(center_id=item.id).first()
            if class_obj:
                center_data['class_start_date'] = class_obj.started_date.strftime('%Y-%m-%d %H:%M:%S') if class_obj.started_date else None
                center_data['class_end_date'] = class_obj.end_date.strftime('%Y-%m-%d %H:%M:%S') if class_obj.end_date else None
                center_data['total_present_students'] = class_obj.avilable_students
            else:
                center_data['total_present_students'] = 0
            
            all_centers.append(center_data)
            
    elif status_param == CLASS_STATUS_CANCEL:
        # Cancel classes
        canceled_classes = ClassCancelByTeacher.objects.filter(
            starting_date__date__lte=today,
            ending_date__date__gte=today
        ).select_related('center')
        
        center_ids = [cc.center_id for cc in canceled_classes if cc.center_id]
        
        centers = Center.objects.filter(
            id__in=center_ids
        ).select_related('district', 'vidhan_sabha', 'panchayat', 'village')
        
        for item in centers:
            center_data = build_center_data(item)
            all_centers.append(center_data)
            
    else:
        # Upcoming classes
        classes = ClassModel.objects.filter(
            started_date__date=today
        ).select_related('center')
        
        center_ids = [cls.center_id for cls in classes if cls.center_id]
        
        centers = Center.objects.exclude(
            id__in=center_ids
        ).select_related('district', 'vidhan_sabha', 'panchayat', 'village')
        
        for item in centers:
            center_data = build_center_data(item)
            all_centers.append(center_data)
    
    return all_centers

def get_centers_for_regional_admin(status_param, user_id, today):
    """Get centers for regional admin"""
    all_centers = []
    
    if status_param == CLASS_STATUS_ACTIVE or status_param == CLASS_STATUS_COMPLETED:
        # Active or Completed classes
        classes = ClassModel.objects.filter(
            started_date__date=today,
            status=status_param
        ).select_related('center')
        
        center_ids = [cls.center_id for cls in classes if cls.center_id]
        
        centers = Center.objects.filter(
            id__in=center_ids,
            assigned_regional_admin=user_id
        ).select_related('district', 'vidhan_sabha', 'panchayat', 'village')
        
        for item in centers:
            center_data = build_center_data(item)
            
            # Get class data for this center
            class_obj = classes.filter(center_id=item.id).first()
            if class_obj:
                center_data['class_start_date'] = class_obj.started_date.strftime('%Y-%m-%d %H:%M:%S') if class_obj.started_date else None
                center_data['class_end_date'] = class_obj.end_date.strftime('%Y-%m-%d %H:%M:%S') if class_obj.end_date else None
                center_data['total_present_students'] = class_obj.avilable_students
            else:
                center_data['total_present_students'] = 0
            
            all_centers.append(center_data)
            
    elif status_param == CLASS_STATUS_CANCEL:
        # Cancel classes for regional admin
        canceled_classes = ClassCancelByTeacher.objects.filter(
            starting_date__date__lte=today,
            ending_date__date__gte=today
        ).select_related('center')
        
        center_ids = [cc.center_id for cc in canceled_classes if cc.center_id]
        
        centers = Center.objects.filter(
            id__in=center_ids,
            assigned_regional_admin=user_id
        ).select_related('district', 'vidhan_sabha', 'panchayat', 'village')
        
        for item in centers:
            center_data = build_center_data(item)
            all_centers.append(center_data)
            
    else:
        # Upcoming classes for regional admin
        classes = ClassModel.objects.filter(
            started_date__date=today
        ).select_related('center')
        
        center_ids = [cls.center_id for cls in classes if cls.center_id]
        
        centers = Center.objects.exclude(
            id__in=center_ids
        ).filter(
            assigned_regional_admin=user_id
        ).select_related('district', 'vidhan_sabha', 'panchayat', 'village')
        
        for item in centers:
            center_data = build_center_data(item)
            all_centers.append(center_data)
    
    return all_centers


# ========== ROLE HELPERS ==========
def get_role_by_code(role_code):
    """Get role by code"""
    try:
        return Role.objects.get(role_code=role_code, status=True)
    except Role.DoesNotExist:
        return None


def get_role_by_id(role_id):
    """Get role by ID"""
    try:
        return Role.objects.get(id=role_id, status=True)
    except Role.DoesNotExist:
        return None


# CENTER SECTION ---------------------------------------------------------

def get_all_centers(userId, type):
    """
    Get all centers with optional filtering by userId and type
    """
    logger.info(f"CenterUtils : GetAllCenters : Started")
    
    try:
        centers = []
        
        # Using raw SQL to replicate the .NET LINQ query exactly
        if userId == 0 and type == 0:
            sql = """
                SELECT 
                    c.Id,
                    c.StartedDate,
                    c.CreatedDate,
                    c.ClassStatus,
                    c.CenterGuidId,
                    c.CenterName,
                    c.AssignedTeachers,
                    c.AssignedRegionalAdmin,
                    c.Status,
                    c.PanchayatId,
                    c.DistrictId,
                    c.VidhanSabhaId,
                    c.VillageId,
                    p.Name as PanchayatName,
                    d.Name as DistrictName,
                    v.Name as VidhanSabhaName,
                    vi.Name as VillageName,
                    u1.Name as TeacherName,
                    u2.Name as RegionalAdminName,
                    (SELECT COUNT(*) FROM Student s WHERE s.CenterId = c.Id AND s.Status = 1) as TotalStudents
                FROM Center c
                LEFT JOIN Users u1 ON c.AssignedTeachers = u1.Id AND u1.Status = 1
                LEFT JOIN District d ON c.DistrictId = d.Id AND d.Status = 1
                LEFT JOIN VidhanSabha v ON c.VidhanSabhaId = v.Id AND v.Status = 1
                LEFT JOIN Panchayat p ON c.PanchayatId = p.Id AND p.Status = 1
                LEFT JOIN Village vi ON c.VillageId = vi.Id AND vi.Status = 1
                LEFT JOIN Users u2 ON c.AssignedRegionalAdmin = u2.Id AND u2.Status = 1
                WHERE c.Status = 1
                ORDER BY c.Id DESC
            """
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                for row in rows:
                    center_dict = dict(zip(columns, row))
                    centers.append(center_dict)
        else:
            sql = """
                SELECT 
                    c.Id,
                    c.StartedDate,
                    c.CreatedDate,
                    c.ClassStatus,
                    c.CenterGuidId,
                    c.CenterName,
                    c.AssignedTeachers,
                    c.AssignedRegionalAdmin,
                    c.Status,
                    c.PanchayatId,
                    c.DistrictId,
                    c.VidhanSabhaId,
                    c.VillageId,
                    p.Name as PanchayatName,
                    d.Name as DistrictName,
                    v.Name as VidhanSabhaName,
                    vi.Name as VillageName,
                    u1.Name as TeacherName,
                    u2.Name as RegionalAdminName,
                    (SELECT COUNT(*) FROM Student s WHERE s.CenterId = c.Id AND s.Status = 1) as TotalStudents
                FROM Center c
                INNER JOIN Users u1 ON c.AssignedTeachers = u1.Id AND u1.Status = 1
                INNER JOIN District d ON c.DistrictId = d.Id AND d.Status = 1
                INNER JOIN VidhanSabha v ON c.VidhanSabhaId = v.Id AND v.Status = 1
                INNER JOIN Panchayat p ON c.PanchayatId = p.Id AND p.Status = 1
                LEFT JOIN Village vi ON c.VillageId = vi.Id AND vi.Status = 1
                LEFT JOIN Users u2 ON c.AssignedRegionalAdmin = u2.Id AND u2.Status = 1
                WHERE c.AssignedRegionalAdmin = %s AND c.Status = 1
                ORDER BY c.Id DESC
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [userId])
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                for row in rows:
                    center_dict = dict(zip(columns, row))
                    centers.append(center_dict)
        
        # Convert to DTO format
        result = []
        for center in centers:
            dto = convert_center_to_all_center_dto(center)
            result.append(dto)
        
        logger.info(f"CenterUtils : GetAllCenters : End")
        return result
        
    except Exception as e:
        logger.error(f"CenterUtils : GetAllCenters : {str(e)}")
        raise e

def convert_center_to_all_center_dto(center_dict):
    """
    Convert Center dictionary to AllCenterDto format
    Exactly matching the .NET ConvertCenterToAllCenterDto method
    """
    # Get StartedDate
    started_date = center_dict.get('StartedDate')
    date_str = started_date.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] if started_date else None
    
    # Get TotalStudents
    total_students = center_dict.get('TotalStudents')
    if total_students is None:
        total_students = 0
    
    # Get Status (bool? in Center)
    status = center_dict.get('Status')
    
    # Get ClassStatus (bool? in Center)
    class_status = center_dict.get('ClassStatus')
    
    return {
        'id': center_dict.get('Id'),
        'centerName': center_dict.get('CenterName'),
        'date': date_str,
        'classDate': center_dict.get('CreatedDate'),
        'classEndDate': None,  # This would come from ClassModel if available
        'classStatus': class_status,
        'status': status,
        'districtName': center_dict.get('DistrictName'),
        'vidhanSabhaName': center_dict.get('VidhanSabhaName'),
        'totalPresentStudents': 0,  # Set default as in .NET
        'totalActiveStudents': 0,   # Set default as in .NET
        'totalStudents': total_students,
        'panchayatName': center_dict.get('PanchayatName'),
        'villageName': center_dict.get('VillageName'),
        'vidhanSabhaId': center_dict.get('VidhanSabhaId'),
        'villageId': center_dict.get('VillageId'),
        'districtId': center_dict.get('DistrictId'),
        'panchayatId': center_dict.get('PanchayatId'),
        'assignedTeacher': center_dict.get('AssignedTeachers'),
        'teacherName': center_dict.get('TeacherName'),
        'assignedRegionalAdmin': center_dict.get('AssignedRegionalAdmin'),
        'regionalAdminName': center_dict.get('RegionalAdminName'),
    }

# Alternative approach using Django ORM instead of raw SQL
def get_all_centers_orm(userId, type):
    """
    Get all centers with optional filtering using Django ORM
    """
    logger.info(f"CenterUtils : GetAllCenters : Started")
    
    try:
        # Subquery for teacher name
        teacher_subquery = User.objects.filter(
            id=OuterRef('assigned_teachers')
        ).values('name')[:1]
        
        # Subquery for regional admin name
        regional_admin_subquery = User.objects.filter(
            id=OuterRef('assigned_regional_admin')
        ).values('name')[:1]
        
        # Subquery for total students
        student_count_subquery = Student.objects.filter(
            center_id=OuterRef('id'),
            status=True
        ).values('center_id').annotate(
            count=Count('id')
        ).values('count')[:1]
        
        # Base queryset
        queryset = Center.objects.select_related(
            'district', 'vidhan_sabha', 'panchayat', 'village'
        ).annotate(
            teacher_name=Subquery(teacher_subquery),
            regional_admin_name=Subquery(regional_admin_subquery),
            total_students=Subquery(student_count_subquery, output_field=models.IntegerField())
        ).order_by('-id')
        
        # Apply filter if userId is provided
        if userId != 0 and type != 0:
            queryset = queryset.filter(assigned_regional_admin=userId)
        
        # Convert to DTO
        result = []
        for center in queryset:
            dto = {
                'id': center.id,
                'centerName': center.center_name,
                'date': center.started_date.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] if center.started_date else None,
                'classDate': center.created_date,
                'classEndDate': None,
                'classStatus': center.class_status,
                'status': center.status,
                'districtName': center.district.name if center.district else None,
                'vidhanSabhaName': center.vidhan_sabha.name if center.vidhan_sabha else None,
                'totalPresentStudents': 0,
                'totalActiveStudents': 0,
                'totalStudents': getattr(center, 'total_students', 0) or 0,
                'panchayatName': center.panchayat.name if center.panchayat else None,
                'villageName': center.village.name if center.village else None,
                'vidhanSabhaId': center.vidhan_sabha_id,
                'villageId': center.village_id,
                'districtId': center.district_id,
                'panchayatId': center.panchayat_id,
                'assignedTeacher': center.assigned_teachers,
                'teacherName': getattr(center, 'teacher_name', None),
                'assignedRegionalAdmin': center.assigned_regional_admin,
                'regionalAdminName': getattr(center, 'regional_admin_name', None),
            }
            result.append(dto)
        
        logger.info(f"CenterUtils : GetAllCenters : End")
        return result
        
    except Exception as e:
        logger.error(f"CenterUtils : GetAllCenters : {str(e)}")
        raise e
    
def get_center_by_id(center_id):
    """Get center by ID with related data"""
    logger.info(f"CenterHelper : GetCenteryId : Started")
    
    try:
        sql = """
            SELECT 
                c.Id,
                c.CenterName,
                c.ClassStatus,
                c.Status,
                c.StartedDate as EnrollmentDate,
                c.VidhanSabhaId,
                c.DistrictId,
                c.PanchayatId,
                c.VillageId,
                d.Name as DistrictName,
                v.Name as VidhanSabhaName,
                vi.Name as VillageName,
                p.Name as PanchayatName,
                c.AssignedRegionalAdmin as RegionalAdminId,
                u.Name as RegionalAdminName,
                (SELECT COUNT(*) FROM Student s WHERE s.CenterId = c.Id AND s.Status = 1) as TotalStudents,
                c.AssignedTeachers as TeacherId
            FROM Center c
            LEFT JOIN District d ON c.DistrictId = d.Id AND d.Status = 1
            LEFT JOIN VidhanSabha v ON c.VidhanSabhaId = v.Id AND v.Status = 1
            LEFT JOIN Panchayat p ON c.PanchayatId = p.Id AND p.Status = 1
            LEFT JOIN Village vi ON c.VillageId = vi.Id AND vi.Status = 1
            LEFT JOIN Users u ON c.AssignedRegionalAdmin = u.Id AND u.Status = 1
            WHERE c.Id = %s AND c.Status = 1
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql, [center_id])
            row = cursor.fetchone()
            
            if row:
                columns = [col[0] for col in cursor.description]
                center_dict = dict(zip(columns, row))
                
                # Get teacher details (UserDto)
                if center_dict.get('TeacherId'):
                    teacher_sql = """
                        SELECT Id, Name, PhoneNumber, Picture
                        FROM Users
                        WHERE Id = %s AND Status = 1
                    """
                    cursor.execute(teacher_sql, [center_dict.get('TeacherId')])
                    teacher_row = cursor.fetchone()
                    if teacher_row:
                        teacher_columns = [col[0] for col in cursor.description]
                        teacher_dict = dict(zip(teacher_columns, teacher_row))
                        # Map to UserDto fields
                        center_dict['teacher'] = {
                            'id': teacher_dict.get('Id'),
                            'name': teacher_dict.get('Name'),
                            'phoneNumber': teacher_dict.get('PhoneNumber'),
                            'picture': teacher_dict.get('Picture')
                        }
                
                # Remove TeacherId from response
                center_dict.pop('TeacherId', None)
                
                return center_dict
        
        return None
        
    except Exception as e:
        logger.error(f"CenterHelper : GetCenteryId : {str(e)}")
        raise e

def get_center_by_user_id(user_id):
    """Get center assigned to a teacher"""
    logger.info(f"CenterHelper : GetCenterByUserId : Started")
    
    try:
        sql = """
            SELECT 
                c.Id,
                c.CenterName,
                c.ClassStatus,
                c.Status,
                c.StartedDate as EnrollmentDate,
                c.VidhanSabhaId,
                c.DistrictId,
                c.PanchayatId,
                c.VillageId,
                d.Name as DistrictName,
                v.Name as VidhanSabhaName,
                vi.Name as VillageName,
                p.Name as PanchayatName,
                c.AssignedRegionalAdmin as RegionalAdminId,
                u.Name as RegionalAdminName,
                (SELECT COUNT(*) FROM Student s WHERE s.CenterId = c.Id AND s.Status = 1) as TotalStudents,
                c.AssignedTeachers as TeacherId
            FROM Center c
            LEFT JOIN District d ON c.DistrictId = d.Id AND d.Status = 1
            LEFT JOIN VidhanSabha v ON c.VidhanSabhaId = v.Id AND v.Status = 1
            LEFT JOIN Panchayat p ON c.PanchayatId = p.Id AND p.Status = 1
            LEFT JOIN Village vi ON c.VillageId = vi.Id AND vi.Status = 1
            LEFT JOIN Users u ON c.AssignedRegionalAdmin = u.Id AND u.Status = 1
            WHERE c.AssignedTeachers = %s AND c.Status = 1
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql, [user_id])
            row = cursor.fetchone()
            
            if row:
                columns = [col[0] for col in cursor.description]
                center_dict = dict(zip(columns, row))
                
                # Get teacher details (UserDto)
                if center_dict.get('TeacherId'):
                    teacher_sql = """
                        SELECT Id, Name, PhoneNumber, Picture
                        FROM Users
                        WHERE Id = %s AND Status = 1
                    """
                    cursor.execute(teacher_sql, [center_dict.get('TeacherId')])
                    teacher_row = cursor.fetchone()
                    if teacher_row:
                        teacher_columns = [col[0] for col in cursor.description]
                        teacher_dict = dict(zip(teacher_columns, teacher_row))
                        center_dict['teacher'] = {
                            'id': teacher_dict.get('Id'),
                            'name': teacher_dict.get('Name'),
                            'phoneNumber': teacher_dict.get('PhoneNumber'),
                            'picture': teacher_dict.get('Picture')
                        }
                
                center_dict.pop('TeacherId', None)
                return center_dict
        
        return None
        
    except Exception as e:
        logger.error(f"CenterHelper : GetCenterByUserId : {str(e)}")
        raise e

def get_all_center_attendance(user_id, date, offset, limit):
    """Get all center attendance"""
    logger.info(f"CenterHelper : GetAllCenterAttendance : Started")
    
    try:
        # Parse the date
        if isinstance(date, str):
            date_obj = parse_any_datetime(date)
            date_obj = date_obj.date() if date_obj else datetime.now().date()
        elif hasattr(date, 'date'):
            date_obj = date.date()
        else:
            date_obj = date
        
        # Get user type
        try:
            user = User.objects.get(id=user_id)
            user_type = user.type
        except User.DoesNotExist:
            logger.error(f"User not found with ID: {user_id}")
            return []
        
        # Get centers based on user type - order by id descending
        if user_type == 1:
            centers = Center.objects.all().order_by('-id')
        else:
            centers = Center.objects.filter(
                assigned_regional_admin=user_id
            ).order_by('-id')
        
        # Apply pagination
        if limit > 0:
            centers = centers[offset:offset + limit]
        
        result = []
        
        for center in centers:
            # Get class for this center on the given date
            class_obj = ClassModel.objects.filter(
                center_id=center.id,
                started_date__date=date_obj
            ).first()
            
            # Get teacher name
            teacher_name = None
            if center.assigned_teachers:
                try:
                    teacher = User.objects.get(id=center.assigned_teachers)
                    teacher_name = teacher.name
                except User.DoesNotExist:
                    pass
            
            # Get regional admin name
            regional_admin_name = None
            if center.assigned_regional_admin:
                try:
                    regional_admin = User.objects.get(id=center.assigned_regional_admin)
                    regional_admin_name = regional_admin.name
                except User.DoesNotExist:
                    pass
            
            center_type = 1 if class_obj else 2
            
            center_data = {
                'id': center.id,
                'centerName': center.center_name,
                'type': center_type,
                'classStartedDate': class_obj.started_date if class_obj else None,
                'classEndDate': class_obj.end_date if class_obj else None,
                'totalStudents': class_obj.total_students if class_obj else 0,
                'presentStudents': class_obj.avilable_students if class_obj else 0,
                'teacherName': teacher_name,
                'regionalAdminName': regional_admin_name,
                'startDate': None,
                'endDate': None,
                'reason': None
            }
            
            if center_type == 2:
                holiday = Holidays.objects.filter(
                    center_id=center.id,
                    start_date__date__lte=date_obj,
                    end_date__date__gte=date_obj
                ).first()
                
                if holiday:
                    center_data['type'] = 3
                    center_data['reason'] = 'Holiday'
                    center_data['startDate'] = holiday.start_date
                    center_data['endDate'] = holiday.end_date
                
                cancel = ClassCancelByTeacher.objects.filter(
                    center_id=center.id,
                    starting_date__date__lte=date_obj,
                    ending_date__date__gte=date_obj
                ).first()
                
                if cancel:
                    center_data['type'] = 4
                    center_data['reason'] = 'Class cancel by teacher'
                    center_data['startDate'] = cancel.starting_date
                    center_data['endDate'] = cancel.ending_date
            
            result.append(center_data)
        
        logger.info(f"CenterHelper : GetAllCenterAttendance : End")
        return result
        
    except Exception as e:
        logger.error(f"CenterHelper : GetAllCenterAttendance : {str(e)}")
        raise e

def get_total_attendance_count_of_center(user_id, date):
    """Get total attendance count of center """
    logger.info(f"CenterHelper : GetTotalAttendanceCountOfCenter : Started")
    
    try:
        # Parse the date
        if isinstance(date, str):
            date_obj = parse_any_datetime(date)
            date_obj = date_obj.date() if date_obj else datetime.now().date()
        elif hasattr(date, 'date'):
            date_obj = date.date()
        else:
            date_obj = date
        
        # Get user type
        try:
            user = User.objects.get(id=user_id)
            user_type = user.type
        except User.DoesNotExist:
            logger.error(f"User not found with ID: {user_id}")
            return {
                "NotStarted": 0,
                "NoEndDateWithNoAttendance": 0,
                "NoEndDateWithAttendance": 0,
                "Completed": 0,
                "NoAttendance": 0,
            }
        
        # Get centers based on user type
        if user_type == 1:  # SuperAdmin
            centers = Center.objects.all()
        else:  # Regional Admin (Type 2)
            centers = Center.objects.filter(assigned_regional_admin=user_id)
        
        # Initialize counters
        not_started = 0
        end_date_with_no_attendance = 0
        end_date_with_attendance = 0
        completed = 0
        no_attendance = 0
        
        for center in centers:
            # Check if class exists for this center on the given date
            class_obj = ClassModel.objects.filter(
                center_id=center.id,
                started_date__date=date_obj
            ).first()
            
            if class_obj is None:
                # No class exists for this center on this date
                not_started += 1
            else:
                # Class exists, check its status
                if class_obj.avilable_students == 0 and class_obj.end_date is None:
                    # Class has started but no attendance and not ended
                    end_date_with_no_attendance += 1
                elif class_obj.avilable_students > 0 and class_obj.end_date is None:
                    # Class has started with attendance and not ended
                    end_date_with_attendance += 1
                elif class_obj.avilable_students > 0 and class_obj.end_date is not None:
                    # Class completed with attendance
                    completed += 1
                elif class_obj.avilable_students == 0 and class_obj.end_date is not None:
                    # Class completed with no attendance
                    no_attendance += 1
        
        result = {
            "NotStarted": not_started,
            "NoEndDateWithNoAttendance": end_date_with_no_attendance,
            "NoEndDateWithAttendance": end_date_with_attendance,
            "Completed": completed,
            "NoAttendance": no_attendance,
        }
        
        logger.info(f"CenterHelper : GetTotalAttendanceCountOfCenter : End")
        return result
        
    except Exception as e:
        logger.error(f"CenterHelper : GetTotalAttendanceCountOfCenter : {str(e)}")
        raise e

def update_center_active_or_deactive(center_log_data):
    """Update center active or deactive status"""
    logger.info(f"CenterHelper : UpdateCenterActiveOrDeactive : Started")
    
    try:
        center_id = center_log_data.get('centerId')
        status = center_log_data.get('status')
        user_id = center_log_data.get('userId')
        reason = center_log_data.get('reason')
        
        # Update center status
        center = Center.objects.filter(id=center_id).first()
        if not center:
            logger.error(f"Center not found with ID: {center_id}")
            return None
        
        center.status = status
        center.updated_on = datetime.now()
        center.updated_by = user_id
        center.save()
        
        # Insert center log
        CenterLog.objects.create(
            center_id=center_id,
            user_id=user_id,
            reason=reason,
            created_on=datetime.now()
        )
        
        logger.info(f"CenterHelper : UpdateCenterActiveOrDeactive : End")
        return {'centerId': center_id, 'status': status}
        
    except Exception as e:
        logger.error(f"CenterHelper : UpdateCenterActiveOrDeactive : {str(e)}")
        raise e
    
def save_center(center_data, request):
    """Save or update center - matches .NET logic"""
    logger.info(f"CenterHelper : SaveCenter : Started")
    
    try:
        center_id = int(center_data.get('Id', 0))
        current_user_id = get_user_id_from_token(request)
        with transaction.atomic():
            if center_id > 0:
                # Update existing center - preserve Status and ClassStatus (matches .NET)
                try:
                    center = Center.objects.get(id=center_id, status=True)

                    # Get old teacher and regional admin for cleanup if needed
                    old_teacher_id = center.assigned_teachers
                    old_regional_admin_id = center.assigned_regional_admin

                    # Update fields
                    if 'CenterName' in center_data and center_data['CenterName'] is not None:
                        center.center_name = center_data['CenterName']
                    if 'AssignedTeachers' in center_data and center_data['AssignedTeachers'] is not None:
                        center.assigned_teachers = center_data['AssignedTeachers']
                    if 'AssignedRegionalAdmin' in center_data and center_data['AssignedRegionalAdmin'] is not None:
                        center.assigned_regional_admin = center_data['AssignedRegionalAdmin']
                    if 'StartedDate' in center_data and center_data['StartedDate'] is not None:
                        center.started_date = center_data['StartedDate']
                    if 'VidhanSabhaId' in center_data and center_data['VidhanSabhaId'] is not None:
                        center.vidhan_sabha_id = center_data['VidhanSabhaId']
                    if 'DistrictId' in center_data and center_data['DistrictId'] is not None:
                        center.district_id = center_data['DistrictId']
                    if 'PanchayatId' in center_data and center_data['PanchayatId'] is not None:
                        center.panchayat_id = center_data['PanchayatId']
                    if 'VillageId' in center_data and center_data['VillageId'] is not None:
                        center.village_id = center_data['VillageId']

                    # Preserve status and class_status (matches .NET)
                    # Status and ClassStatus are preserved

                    center.updated_on = datetime.now()
                    center.updated_by = current_user_id
                    center.save()

                    # If teacher changed, update statuses
                    if old_teacher_id != center.assigned_teachers:
                        # Remove old teacher assignment
                        if old_teacher_id:
                            try:
                                old_teacher = Teacher.objects.filter(user_id=old_teacher_id, status=True).first()
                                if old_teacher:
                                    # Check if teacher is assigned to any other center
                                    other_center = Center.objects.filter(
                                        assigned_teachers=old_teacher_id,
                                        status=True
                                    ).exclude(id=center_id).first()
                                    if not other_center:
                                        old_teacher.assigned_teacher_status = False
                                        old_teacher.assigned_regional_admin_status = False
                                        old_teacher.updated_on = datetime.now()
                                        old_teacher.updated_by = current_user_id
                                        old_teacher.save()
                            except Exception as e:
                                logger.error(f"Error updating old teacher status: {str(e)}")

                        # Update new teacher assignment
                        if center.assigned_teachers:
                            try:
                                new_teacher = Teacher.objects.filter(user_id=center.assigned_teachers, status=True).first()
                                if new_teacher:
                                    new_teacher.assigned_teacher_status = True
                                    new_teacher.assigned_regional_admin_status = True
                                    new_teacher.updated_on = datetime.now()
                                    new_teacher.updated_by = current_user_id
                                    new_teacher.save()

                                    # Save history for new teacher
                                    if new_teacher.user:
                                        CenterAssignUser.objects.create(
                                            center_id=center.id,
                                            user_id=new_teacher.user.id,
                                            date=datetime.now(),
                                            status=True,
                                            created_by=current_user_id,
                                            created_on=datetime.now()
                                        )
                            except Exception as e:
                                logger.error(f"Error updating new teacher status: {str(e)}")

                    # If regional admin changed, update statuses
                    if old_regional_admin_id != center.assigned_regional_admin:
                        # Remove old regional admin assignment
                        if old_regional_admin_id:
                            try:
                                old_regional_admin = RegionalAdmin.objects.filter(user_id=old_regional_admin_id, status=True).first()
                                if old_regional_admin:
                                    # Check if regional admin is assigned to any other center
                                    other_center = Center.objects.filter(
                                        assigned_regional_admin=old_regional_admin_id,
                                        status=True
                                    ).exclude(id=center_id).first()
                                    if not other_center:
                                        old_regional_admin.assigned_teacher_status = False
                                        old_regional_admin.assigned_regional_admin_status = False
                                        old_regional_admin.updated_on = datetime.now()
                                        old_regional_admin.updated_by = current_user_id
                                        old_regional_admin.save()
                            except Exception as e:
                                logger.error(f"Error updating old regional admin status: {str(e)}")

                        # Update new regional admin assignment
                        if center.assigned_regional_admin:
                            try:
                                new_regional_admin = RegionalAdmin.objects.filter(user_id=center.assigned_regional_admin, status=True).first()
                                if new_regional_admin:
                                    new_regional_admin.assigned_teacher_status = True
                                    new_regional_admin.assigned_regional_admin_status = True
                                    new_regional_admin.updated_on = datetime.now()
                                    new_regional_admin.updated_by = current_user_id
                                    new_regional_admin.save()

                                    # Save history for new regional admin
                                    if new_regional_admin.user:
                                        CenterAssignUser.objects.create(
                                            center_id=center.id,
                                            user_id=new_regional_admin.user.id,
                                            date=datetime.now(),
                                            status=True,
                                            created_by=current_user_id,
                                            created_on=datetime.now()
                                        )
                            except Exception as e:
                                logger.error(f"Error updating new regional admin status: {str(e)}")

                except Center.DoesNotExist:
                    logger.error(f"Center not found with ID: {center_id}")
                    return None
            else:
                # Insert new center
                center_guid = str(uuid.uuid4())
                created_date = datetime.now()

                # Get teacher and regional admin user IDs
                teacher_user_id = center_data.get('AssignedTeachers')
                regional_admin_user_id = center_data.get('AssignedRegionalAdmin')

                center = Center(
                    center_guid_id=center_guid,
                    center_name=center_data.get('CenterName'),
                    assigned_teachers=teacher_user_id,
                    assigned_regional_admin=regional_admin_user_id,
                    started_date=center_data.get('StartedDate'),
                    vidhan_sabha_id=center_data.get('VidhanSabhaId'),
                    district_id=center_data.get('DistrictId'),
                    panchayat_id=center_data.get('PanchayatId'),
                    village_id=center_data.get('VillageId'),
                    status=True,
                    class_status=False,
                    created_date=created_date,
                    created_on=datetime.now(),
                    created_by=current_user_id
                )
                center.save()
                center_id = center.id

                # Update assigned teacher status (matches .NET)
                if teacher_user_id:
                    try:
                        teacher = Teacher.objects.filter(user_id=teacher_user_id, status=True).first()
                        if teacher:
                            teacher.assigned_teacher_status = True
                            teacher.assigned_regional_admin_status = True
                            teacher.updated_on = datetime.now()
                            teacher.updated_by = current_user_id
                            teacher.save()

                            # Save history of user assign (matches .NET)
                            if teacher.user:
                                CenterAssignUser.objects.create(
                                    center_id=center.id,
                                    user_id=teacher.user.id,
                                    date=datetime.now(),
                                    status=True,
                                    created_by=current_user_id,
                                    created_on=datetime.now()
                                )
                    except Exception as e:
                        logger.error(f"Error updating teacher status: {str(e)}")

                # Update assigned regional admin status (matches .NET)
                if regional_admin_user_id:
                    try:
                        regional_admin = RegionalAdmin.objects.filter(user_id=regional_admin_user_id, status=True).first()
                        if regional_admin:
                            regional_admin.assigned_teacher_status = True
                            regional_admin.assigned_regional_admin_status = True
                            regional_admin.updated_on = datetime.now()
                            regional_admin.updated_by = current_user_id
                            regional_admin.save()

                            # Save history of user assign (matches .NET)
                            if regional_admin.user:
                                CenterAssignUser.objects.create(
                                    center_id=center.id,
                                    user_id=regional_admin.user.id,
                                    date=datetime.now(),
                                    status=True,
                                    created_by=current_user_id,
                                    created_on=datetime.now()
                                )
                    except Exception as e:
                        logger.error(f"Error updating regional admin status: {str(e)}")
        
        return get_center_by_id(center_id)
        
    except Exception as e:
        logger.error(f"CenterHelper : SaveCenter : {str(e)}")
        raise e


# TECHERS SECTION ----------------------------------------------------------
def get_all_teachers(user_id):
    """Get all teachers with optional filtering by userId"""
    logger.info(f"UserHelper : GetRegisteredTeachers : Started")
    
    try:
        if user_id == 0:
            # Get all teachers (Type == 3 and Status == True)
            teachers = Teacher.objects.filter(user__role_id=3, user__status=True).select_related('user').order_by('user__name')
        else:
            # Get teachers assigned to centers under this regional admin
            # Find center IDs where AssignedRegionalAdmin = user_id
            center_ids = Center.objects.filter(assigned_regional_admin=user_id).values_list('assigned_teachers', flat=True)
            teachers = Teacher.objects.filter(user__id__in=center_ids, user__role_id=3, user__status=True).select_related('user').order_by('user__name')
        
        result = []
        for teacher in teachers:
            user = teacher.user
            if user:
                teacher_dto = {
                    'id': user.id,
                    'name': user.name,
                    'profile': user.picture.url if user.picture else None,
                    'phoneNumber': user.phone_number,
                    'assigned': teacher.assigned_teacher_status if teacher.assigned_teacher_status is not None else False
                }
                result.append(teacher_dto)
        
        logger.info(f"UserHelper : GetRegisteredTeachers : End")
        return result
        
    except Exception as e:
        logger.error(f"UserHelper : GetRegisteredTeachers : {str(e)}")
        raise e


# USER SECTION---------------------------------------------------------

def login_user(mobile_number, password):
    """Authenticate user - EXACT match to .NET LoginUser"""
    logger.info(f"UserRepository : LoginUser : Started")
    
    try:
        # Hash password using SHA256 - matches .NET EncryptionUtility.GetHashPassword
        hashed_password = hash_password(password)
        
        # Get user by phone number and password
        user = User.objects.filter(
            phone_number=mobile_number,
            password=hashed_password,
            status=True
        ).select_related('role').first()
        
        if not user:
            logger.info(f"UserRepository : LoginUser : End - User not found")
            return None
        
        # Update last login time - save as datetime then format for response
        user.last_login_time = datetime.now()
        user.save(update_fields=['last_login_time'])
        
        # Generate token (matches .NET)
        token = AccessToken()
        token['user_id'] = user.id
        token['user_type'] = user.role.role_code if user.role else None
        token['mobile_number'] = mobile_number
        token['name'] = user.name or mobile_number
        token.set_exp(lifetime=timedelta(days=30))
        
        # Set token on user object (matches .NET)
        user.token = str(token)
        user.save(update_fields=['token'])
        
        # Format last login time for response - matches .NET format: M/d/yyyy h:mm:ss tt
        # Example: 7/16/2026 2:56:27 PM
        last_login_formatted = format_dotnet_datetime(user.last_login_time)
        
        # Build base response from User table
        response_data = {
            "id": user.id,
            "enrolmentRollId": user.enrolment_roll_id,
            "password": None,
            "name": user.name,
            "token": str(token),
            "deviceId": user.device_id,
            "type": user.role_id,
            "status": user.status,
            "email": user.email,
            "phoneNumber": user.phone_number,
            "picture": user.picture.url if user.picture else None,
            "whatsApp": user.whats_app,
            "lastLoginTime": last_login_formatted,
            "roleId": user.role_id,
            "createdOn": format_dotnet_datetime(user.created_on) if user.created_on else None,
            "createdBy": user.created_by,
            # Default values for role-specific fields
            "age": None,
            "gender": None,
            "contact": None,
            "dateOfBirth": None,
            "fullAddress": None,
            "education": None,
            "enrollmentDate": None,
            "guardianName": None,
            "guardianNumber": None,
            "assignedTeacherStatus": None,
            "assignedRegionalAdminStatus": None,
            "vidhanSabhaId": None,
            "districtId": None,
            "villageId": None,
            "panchayatId": None,
            "count": None,
            "centerId": None,
            "listOfPanchayatId": None,
            "district": None,
            "vidhanSabha": None,
            "panchayat": None,
            "village": None,
            "regionalAdminPanchayat": None,
            "center": None,
            "centers": None,
            "centerAssignUser": None
        }
        
        # Add role-specific data based on role
        if user.role:
            role_code = user.role.role_code
            
            if role_code == 'SUPER_ADMIN':
                super_admin = SuperAdmin.objects.filter(user=user).first()
                if super_admin:
                    response_data.update({
                        "age": super_admin.age,
                        "gender": super_admin.gender,
                        "contact": super_admin.contact,
                        "dateOfBirth": super_admin.date_of_birth,
                        "fullAddress": super_admin.full_address,
                        "education": super_admin.education,
                        "enrollmentDate": format_dotnet_datetime(super_admin.enrollment_date) if super_admin.enrollment_date else None,
                        "createdOn": format_dotnet_datetime(super_admin.created_on) if super_admin.created_on else user.created_on,
                    })
                    
            elif role_code == 'REGIONAL_ADMIN':
                regional_admin = RegionalAdmin.objects.filter(user=user).first()
                if regional_admin:
                    # Get list of panchayats
                    list_of_panchayat = []
                    regional_admin_panchayats = RegionalAdminPanchayat.objects.filter(
                        regional_admin=regional_admin,
                        status=True
                    ).select_related('panchayat')
                    
                    for rap in regional_admin_panchayats:
                        if rap.panchayat:
                            list_of_panchayat.append({
                                'id': rap.panchayat.id,
                                'panchayatGuidId': str(rap.panchayat.panchayat_guid_id) if rap.panchayat.panchayat_guid_id else '00000000-0000-0000-0000-000000000000',
                                'name': rap.panchayat.name,
                                'status': rap.panchayat.status,
                                'createdOn': format_dotnet_datetime(rap.panchayat.created_on) if rap.panchayat.created_on else None,
                                'createdBy': rap.panchayat.created_by,
                                'districtId': rap.panchayat.district_id or 0,
                                'vidhanSabhaId': rap.panchayat.vidhan_sabha_id or 0
                            })
                    
                    # Get list of centers
                    list_of_centers = []
                    centers = Center.objects.filter(assigned_regional_admin=regional_admin.id)
                    for center in centers:
                        list_of_centers.append({
                            'id': center.id,
                            'centerGuidId': center.center_guid_id,
                            'centerName': center.center_name,
                            'assignedTeachers': center.assigned_teachers,
                            'assignedRegionalAdmin': center.assigned_regional_admin,
                            'startedDate': format_dotnet_datetime(center.started_date) if center.started_date else None,
                            'vidhanSabhaId': center.vidhan_sabha_id or 0,
                            'districtId': center.district_id or 0,
                            'panchayatId': center.panchayat_id or 0,
                            'villageId': center.village_id
                        })
                    
                    response_data.update({
                        "age": regional_admin.age,
                        "gender": regional_admin.gender,
                        "contact": regional_admin.contact,
                        "dateOfBirth": regional_admin.date_of_birth,
                        "fullAddress": regional_admin.full_address,
                        "education": regional_admin.education,
                        "enrollmentDate": format_dotnet_datetime(regional_admin.enrollment_date) if regional_admin.enrollment_date else None,
                        "guardianName": regional_admin.guardian_name,
                        "guardianNumber": regional_admin.guardian_number,
                        "assignedTeacherStatus": regional_admin.assigned_teacher_status,
                        "assignedRegionalAdminStatus": regional_admin.assigned_regional_admin_status,
                        "vidhanSabhaId": regional_admin.vidhan_sabha_id,
                        "districtId": regional_admin.district_id,
                        "villageId": regional_admin.village_id,
                        "panchayatId": regional_admin.panchayat_id,
                        "listOfPanchayatId": [rap.panchayat_id for rap in regional_admin_panchayats if rap.panchayat_id],
                        "regionalAdminPanchayat": list_of_panchayat,
                        "centers": list_of_centers,
                        "createdOn": format_dotnet_datetime(regional_admin.created_on) if regional_admin.created_on else user.created_on,
                    })
                    
            elif role_code == 'TEACHER':
                teacher = Teacher.objects.filter(user=user).first()
                if teacher:
                    # Get center data
                    center_data = None
                    if teacher.center:
                        center = teacher.center
                        center_data = {
                            'id': center.id,
                            'centerGuidId': center.center_guid_id,
                            'centerName': center.center_name,
                            'classStatus': center.class_status,
                            'status': center.status,
                            'createdDate': format_dotnet_datetime(center.created_date) if center.created_date else None,
                            'startedDate': format_dotnet_datetime(center.started_date) if center.started_date else None,
                            'assignedTeachers': center.assigned_teachers,
                            'assignedRegionalAdmin': center.assigned_regional_admin,
                            'vidhanSabhaId': center.vidhan_sabha_id or 0,
                            'districtId': center.district_id or 0,
                            'panchayatId': center.panchayat_id or 0,
                            'villageId': center.village_id
                        }
                    
                    response_data.update({
                        "age": teacher.age,
                        "gender": teacher.gender,
                        "contact": teacher.contact,
                        "dateOfBirth": teacher.date_of_birth,
                        "fullAddress": teacher.full_address,
                        "education": teacher.education,
                        "enrollmentDate": format_dotnet_datetime(teacher.enrollment_date) if teacher.enrollment_date else None,
                        "guardianName": teacher.guardian_name,
                        "guardianNumber": teacher.guardian_number,
                        "count": teacher.count,
                        "assignedTeacherStatus": teacher.assigned_teacher_status,
                        "assignedRegionalAdminStatus": teacher.assigned_regional_admin_status,
                        "vidhanSabhaId": teacher.vidhan_sabha_id,
                        "districtId": teacher.district_id,
                        "villageId": teacher.village_id,
                        "panchayatId": teacher.panchayat_id,
                        "centerId": teacher.center_id,
                        "center": center_data,
                        "createdOn": format_dotnet_datetime(teacher.created_on) if teacher.created_on else user.created_on,
                    })
        
        logger.info(f"UserRepository : LoginUser : End")
        return response_data
        
    except Exception as e:
        logger.error(f"UserRepository : LoginUser : {str(e)}")
        raise e
    
        
# helper.py - Updated save_user function with RoleId fix

def save_user(user_data):
    """Save or update user - matches .NET SaveLogin logic exactly"""
    logger.info(f"UserHelper : SaveLogin : Started")
    
    try:
        user_id = int(user_data.get('Id', 0))
        print(f"Saving user with ID: {user_id}")
        
        # Wrap everything in atomic transaction
        with transaction.atomic():
            if user_id > 0:
                # Update existing user
                user = User.objects.get(id=user_id)
                
                # Preserve values (matches .NET logic)
                existing_status = user.status
                existing_created_on = user.created_on
                existing_password = user.password
                existing_role_id = user.role_id
                
                # Update fields based on user type
                user_type = int(user_data.get('Type'))
                
                if user_type == 1:  # SuperAdmin - can change anything
                    # Update all fields
                    if 'Name' in user_data and user_data['Name'] is not None:
                        user.name = user_data['Name']
                    if 'Email' in user_data and user_data['Email'] is not None:
                        user.email = user_data['Email']
                    if 'PhoneNumber' in user_data and user_data['PhoneNumber'] is not None:
                        user.phone_number = user_data['PhoneNumber']
                    if 'WhatsApp' in user_data and user_data['WhatsApp'] is not None:
                        user.whats_app = user_data['WhatsApp']
                    if 'Status' in user_data and user_data['Status'] is not None:
                        user.status = user_data['Status']
                    if 'Picture' in user_data and user_data['Picture'] is not None:
                        picture_data = user_data['Picture']
                        # Handle file upload - if it's a file object, save it
                        if hasattr(picture_data, 'read'):  # It's a file object
                            picture_url = save_profile_image(picture_data, user_id)
                            if picture_url:
                                user.picture = picture_url
                        else:
                            # It's a URL string
                            user.picture = picture_data
                    if 'DeviceId' in user_data and user_data['DeviceId'] is not None:
                        user.device_id = user_data['DeviceId']
                    if 'Token' in user_data and user_data['Token'] is not None:
                        user.token = user_data['Token']
                    if 'EnrolmentRollId' in user_data and user_data['EnrolmentRollId'] is not None:
                        user.enrolment_roll_id = user_data['EnrolmentRollId']
                    if 'Password' in user_data and user_data['Password'] != existing_password:
                        user.password = user_data['Password']
                else:
                    # Non-superadmin: only update specific fields (matches .NET ConvertUpdateUsertoToUser)
                    if 'Email' in user_data and user_data['Email'] is not None:
                        user.email = user_data['Email']
                    if 'PhoneNumber' in user_data and user_data['PhoneNumber'] is not None:
                        user.phone_number = user_data['PhoneNumber']
                    if 'Name' in user_data and user_data['Name'] is not None:
                        user.name = user_data['Name']
                    # Allow Picture update for RegionalAdmin and Teacher (fixes bug where picture wasn't saving)
                    if 'Picture' in user_data and user_data['Picture'] is not None:
                        picture_data = user_data['Picture']
                        # Handle file upload - if it's a file object, save it
                        if hasattr(picture_data, 'read'):  # It's a file object
                            picture_url = save_profile_image(picture_data, user_id)
                            if picture_url:
                                user.picture = picture_url
                        else:
                            # It's a URL string
                            user.picture = picture_data
                    
                    # Preserve these fields (matches .NET)
                    user.enrolment_roll_id = user_data.get('EnrolmentRollId') or user.enrolment_roll_id
                    user.status = existing_status
                    user.created_on = existing_created_on
                    user.password = user_data.get('Password') or existing_password
                
                user.updated_on = datetime.now()
                user.updated_by = user_data.get('CreatedBy') or user_id
                user.save()
                
                # Update role-specific table based on type
                if user_type == 2:  # RegionalAdmin
                    regional_admin = RegionalAdmin.objects.filter(user=user).first()
                    if regional_admin:
                        if 'DateOfBirth' in user_data and user_data['DateOfBirth'] is not None:
                            regional_admin.date_of_birth = user_data['DateOfBirth']
                        if 'GuardianName' in user_data and user_data['GuardianName'] is not None:
                            regional_admin.guardian_name = user_data['GuardianName']
                        if 'GuardianNumber' in user_data and user_data['GuardianNumber'] is not None:
                            regional_admin.guardian_number = user_data['GuardianNumber']
                        if 'Age' in user_data and user_data['Age'] is not None:
                            regional_admin.age = user_data['Age']
                        if 'Gender' in user_data and user_data['Gender'] is not None:
                            regional_admin.gender = user_data['Gender']
                        if 'Contact' in user_data and user_data['Contact'] is not None:
                            regional_admin.contact = user_data['Contact']
                        if 'FullAddress' in user_data and user_data['FullAddress'] is not None:
                            regional_admin.full_address = user_data['FullAddress']
                        if 'Education' in user_data and user_data['Education'] is not None:
                            regional_admin.education = user_data['Education']
                        if 'DistrictId' in user_data and user_data['DistrictId'] is not None:
                            regional_admin.district_id = user_data['DistrictId']
                        if 'VidhanSabhaId' in user_data and user_data['VidhanSabhaId'] is not None:
                            regional_admin.vidhan_sabha_id = user_data['VidhanSabhaId']
                        if 'PanchayatId' in user_data and user_data['PanchayatId'] is not None:
                            regional_admin.panchayat_id = user_data['PanchayatId']
                        if 'VillageId' in user_data and user_data['VillageId'] is not None:
                            regional_admin.village_id = user_data['VillageId']
                        regional_admin.updated_on = datetime.now()
                        regional_admin.updated_by = user_data.get('CreatedBy') or user_id
                        regional_admin.save()
                        
                        # Handle ListOfPanchayatIds for RegionalAdmin
                        list_of_panchayat_ids = user_data.get('ListOfPanchayatIds')
                        if list_of_panchayat_ids:
                            if isinstance(list_of_panchayat_ids, str):
                                panchayat_list = [int(x.strip()) for x in list_of_panchayat_ids.split(',') if x.strip()]
                            else:
                                panchayat_list = list_of_panchayat_ids if isinstance(list_of_panchayat_ids, list) else []
                            
                            if panchayat_list:
                                # Get the regional admin object
                                regional_admin = RegionalAdmin.objects.filter(user=user).first()
                                if regional_admin:
                                    # Soft delete existing records
                                    RegionalAdminPanchayat.objects.filter(
                                        regional_admin=regional_admin
                                    ).update(
                                        status=False,
                                        updated_on=datetime.now(),
                                        updated_by=user_data.get('CreatedBy') or user_id
                                    )
                                    
                                    # Insert new records
                                    for panchayat_id in panchayat_list:
                                        panchayat = Panchayat.objects.filter(id=panchayat_id).first()
                                        if panchayat:
                                            RegionalAdminPanchayat.objects.create(
                                                regional_admin=regional_admin,
                                                panchayat_id=panchayat_id,
                                                panchayat_name=panchayat.name,
                                                status=True,
                                                created_on=datetime.now(),
                                                created_by=user_data.get('CreatedBy') or user_id
                                            )
                
                elif user_type == 3:  # Teacher
                    teacher = Teacher.objects.filter(user=user).first()
                    if teacher:
                        if 'DateOfBirth' in user_data and user_data['DateOfBirth'] is not None:
                            teacher.date_of_birth = user_data['DateOfBirth']
                        if 'GuardianName' in user_data and user_data['GuardianName'] is not None:
                            teacher.guardian_name = user_data['GuardianName']
                        if 'GuardianNumber' in user_data and user_data['GuardianNumber'] is not None:
                            teacher.guardian_number = user_data['GuardianNumber']
                        if 'Age' in user_data and user_data['Age'] is not None:
                            teacher.age = user_data['Age']
                        if 'Gender' in user_data and user_data['Gender'] is not None:
                            teacher.gender = user_data['Gender']
                        if 'Contact' in user_data and user_data['Contact'] is not None:
                            teacher.contact = user_data['Contact']
                        if 'FullAddress' in user_data and user_data['FullAddress'] is not None:
                            teacher.full_address = user_data['FullAddress']
                        if 'Education' in user_data and user_data['Education'] is not None:
                            teacher.education = user_data['Education']
                        if 'DistrictId' in user_data and user_data['DistrictId'] is not None:
                            teacher.district_id = user_data['DistrictId']
                        if 'VidhanSabhaId' in user_data and user_data['VidhanSabhaId'] is not None:
                            teacher.vidhan_sabha_id = user_data['VidhanSabhaId']
                        if 'PanchayatId' in user_data and user_data['PanchayatId'] is not None:
                            teacher.panchayat_id = user_data['PanchayatId']
                        if 'VillageId' in user_data and user_data['VillageId'] is not None:
                            teacher.village_id = user_data['VillageId']
                        if 'Count' in user_data and user_data['Count'] is not None:
                            teacher.count = user_data['Count']
                        
                        # Handle ListOfPanchayatIds for Teacher
                        list_of_panchayat_ids = user_data.get('ListOfPanchayatIds')
                        if list_of_panchayat_ids and teacher:
                            if isinstance(list_of_panchayat_ids, str):
                                panchayat_list = [int(x.strip()) for x in list_of_panchayat_ids.split(',') if x.strip()]
                            else:
                                panchayat_list = list_of_panchayat_ids if isinstance(list_of_panchayat_ids, list) else []
                            
                            if len(panchayat_list) == 1:
                                teacher.panchayat_id = panchayat_list[0]
                        
                        teacher.updated_on = datetime.now()
                        teacher.updated_by = user_data.get('CreatedBy') or user_id
                        teacher.save()
            
            else:
                # Insert new user (matches .NET logic)
                name = user_data.get('Name', '')
                date_of_birth = user_data.get('DateOfBirth', '')
                gender = user_data.get('Gender', '')
                
                enrolment_roll_id = f"{name[:2]}-{date_of_birth}-"
                if gender and gender.lower() == 'male':
                    enrolment_roll_id += 'M'
                else:
                    enrolment_roll_id += 'F'
                
                # Get role
                role = None
                user_type = int(user_data.get('Type'))
                
                # Try to get role by RoleId first (from .NET request)
                if user_type:
                    role = Role.objects.filter(id=user_type).first()
                    
                # Create user with role
                picture_data = user_data.get('Picture')
                picture_url = None
                if picture_data and hasattr(picture_data, 'read'):  # It's a file object
                    # We need to save user first to get user_id, then update picture
                    pass  # Will handle after user.save()
                
                user = User(
                    enrolment_roll_id=enrolment_roll_id,
                    name=name,
                    email=user_data.get('Email'),
                    password=user_data.get('Password'),
                    phone_number=user_data.get('PhoneNumber'),
                    whats_app=user_data.get('WhatsApp'),
                    status=True,
                    picture=None,  # Will set after saving if file upload
                    device_id=user_data.get('DeviceId'),
                    token=user_data.get('Token'),
                    role=role,
                    created_on=datetime.now(),
                    created_by=user_data.get('CreatedBy') or 1
                )
                user.save()
                user_id = user.id
                
                # Handle picture upload for new user
                if picture_data and hasattr(picture_data, 'read'):  # It's a file object
                    picture_url = save_profile_image(picture_data, user_id)
                    if picture_url:
                        user.picture = picture_url
                        user.save(update_fields=['picture'])
                elif picture_data:
                    # It's a URL string
                    user.picture = picture_data
                    user.save(update_fields=['picture'])
                
                # Create role-specific record
                if user_type == 1:  # SuperAdmin
                    SuperAdmin.objects.create(
                        super_admin_guid_id=str(uuid.uuid4()),
                        user=user,
                        status=True,
                        created_on=datetime.now(),
                        created_by=user_data.get('CreatedBy') or 1
                    )
                
                elif user_type == 2:  # RegionalAdmin
                    regional_admin = RegionalAdmin(
                        regional_admin_guid_id=str(uuid.uuid4()),
                        user=user,
                        age=user_data.get('Age'),
                        gender=user_data.get('Gender'),
                        date_of_birth=user_data.get('DateOfBirth'),
                        contact=user_data.get('Contact'),
                        full_address=user_data.get('FullAddress'),
                        education=user_data.get('Education'),
                        guardian_name=user_data.get('GuardianName'),
                        guardian_number=user_data.get('GuardianNumber'),
                        assigned_teacher_status=False,
                        assigned_regional_admin_status=False,
                        enrollment_date=user_data.get('EnrollmentDate'),
                        district_id=user_data.get('DistrictId'),
                        vidhan_sabha_id=user_data.get('VidhanSabhaId'),
                        panchayat_id=user_data.get('PanchayatId'),
                        village_id=user_data.get('VillageId'),
                        status=True,
                        created_on=datetime.now(),
                        created_by=user_data.get('CreatedBy') or 1
                    )
                    regional_admin.save()
                    
                    # Handle ListOfPanchayatIds for RegionalAdmin
                    list_of_panchayat_ids = user_data.get('ListOfPanchayatIds')
                    if list_of_panchayat_ids:
                        if isinstance(list_of_panchayat_ids, str):
                            panchayat_list = [int(x.strip()) for x in list_of_panchayat_ids.split(',') if x.strip()]
                        else:
                            panchayat_list = list_of_panchayat_ids if isinstance(list_of_panchayat_ids, list) else []
                        
                        for panchayat_id in panchayat_list:
                            panchayat = Panchayat.objects.filter(id=panchayat_id).first()
                            if panchayat:
                                RegionalAdminPanchayat.objects.create(
                                    regional_admin=regional_admin,
                                    panchayat_id=panchayat_id,
                                    panchayat_name=panchayat.name,
                                    status=True,
                                    created_on=datetime.now(),
                                    created_by=user_data.get('CreatedBy') or 1
                                )
                
                elif user_type == 3:  # Teacher
                    teacher = Teacher(
                        teacher_guid_id=str(uuid.uuid4()),
                        user=user,
                        age=user_data.get('Age'),
                        gender=user_data.get('Gender'),
                        date_of_birth=user_data.get('DateOfBirth'),
                        contact=user_data.get('Contact'),
                        full_address=user_data.get('FullAddress'),
                        education=user_data.get('Education'),
                        guardian_name=user_data.get('GuardianName'),
                        guardian_number=user_data.get('GuardianNumber'),
                        count=user_data.get('Count') or 0,
                        assigned_teacher_status=False,
                        assigned_regional_admin_status=False,
                        enrollment_date=user_data.get('EnrollmentDate'),
                        district_id=user_data.get('DistrictId'),
                        vidhan_sabha_id=user_data.get('VidhanSabhaId'),
                        panchayat_id=user_data.get('PanchayatId'),
                        village_id=user_data.get('VillageId'),
                        center_id=user_data.get('CenterId'),
                        status=True,
                        created_on=datetime.now(),
                        created_by=user_data.get('CreatedBy') or 1
                    )
                    teacher.save()
        
        # Get the saved user (outside atomic block)
        return get_user_by_id(user_id)
        
    except User.DoesNotExist:
        logger.error(f"User not found with ID: {user_id}")
        return None
    except Exception as e:
        logger.error(f"UserHelper : SaveLogin : {str(e)}")
        raise e

def get_user_by_id(user_id):
    """Get user by ID with role-specific data"""
    logger.info(f"UserHelper : GetUserById : Started")
    
    try:
        user = User.objects.select_related('role').get(id=user_id)
        
        # Base response
        response = {
            'id': user.id,
            'enrolmentRollId': user.enrolment_roll_id,
            'name': user.name,
            'email': user.email,
            'type': user.role_id,  # role_id as type
            'status': user.status,
            'phoneNumber': user.phone_number,
            'picture': user.picture.url if user.picture else None,
            'whatsApp': user.whats_app,
            'lastLoginTime': user.last_login_time,
            'createdOn': user.created_on.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] if user.created_on else None,
            'createdBy': user.created_by,
            'roleId': user.role_id,
            # Default values for role-specific fields
            'age': None,
            'gender': None,
            'contact': None,
            'dateOfBirth': None,
            'fullAddress': None,
            'education': None,
            'guardianName': None,
            'guardianNumber': None,
            'count': None,
            'assignedTeacherStatus': None,
            'assignedRegionalAdminStatus': None,
            'enrollmentDate': None,
            'districtId': None,
            'vidhanSabhaId': None,
            'villageId': None,
            'panchayatId': None,
            'centerId': None,
            'districtName': None,
            'vidhanSabhaName': None,
            'villageName': None,
            'panchayatName': None,
            'centerName': None,
            'listOfPanchayat': None,
            'listOfCenters': None,
            'center': None,
            'assignedDate': None,
            'centerEnrollmentDate': None
        }
        
        # Super Admin
        if user.role and user.role.role_code == 'SUPER_ADMIN':
            return response
        
        # Regional Admin
        elif user.role and user.role.role_code == 'REGIONAL_ADMIN':
            regional_admin = RegionalAdmin.objects.filter(user=user).first()
            if regional_admin:
                # Get list of panchayats
                list_of_panchayat = []
                regional_admin_panchayats = RegionalAdminPanchayat.objects.filter(
                    regional_admin=regional_admin,
                    status=True
                ).select_related('panchayat')
                
                for rap in regional_admin_panchayats:
                    if rap.panchayat:
                        list_of_panchayat.append({
                            'id': rap.panchayat.id,
                            'panchayatGuidId': rap.panchayat.panchayat_guid_id or '00000000-0000-0000-0000-000000000000',
                            'name': rap.panchayat.name,
                            'status': rap.panchayat.status,
                            'createdOn': rap.panchayat.created_on,
                            'createdBy': rap.panchayat.created_by,
                            'districtId': rap.panchayat.district_id or 0,
                            'vidhanSabhaId': rap.panchayat.vidhan_sabha_id or 0
                        })
                
                # Get list of centers
                list_of_centers = []
                centers = Center.objects.filter(assigned_regional_admin=regional_admin.id)
                for center in centers:
                    list_of_centers.append({
                        'id': center.id,
                        'centerGuidId': center.center_guid_id,
                        'centerName': center.center_name,
                        'assignedTeachers': center.assigned_teachers,
                        'assignedRegionalAdmin': center.assigned_regional_admin,
                        'startedDate': center.started_date,
                        'vidhanSabhaId': center.vidhan_sabha_id or 0,
                        'districtId': center.district_id or 0,
                        'panchayatId': center.panchayat_id or 0,
                        'villageId': center.village_id
                    })
                
                response.update({
                    'age': regional_admin.age,
                    'gender': regional_admin.gender,
                    'dateOfBirth': regional_admin.date_of_birth,
                    'contact': regional_admin.contact,
                    'fullAddress': regional_admin.full_address,
                    'education': regional_admin.education,
                    'guardianName': regional_admin.guardian_name,
                    'guardianNumber': regional_admin.guardian_number,
                    'assignedTeacherStatus': regional_admin.assigned_teacher_status,
                    'assignedRegionalAdminStatus': regional_admin.assigned_regional_admin_status,
                    'enrollmentDate': regional_admin.enrollment_date,
                    'districtId': regional_admin.district_id,
                    'vidhanSabhaId': regional_admin.vidhan_sabha_id,
                    'villageId': regional_admin.village_id,
                    'panchayatId': regional_admin.panchayat_id,
                    'districtName': regional_admin.district.name if regional_admin.district else None,
                    'vidhanSabhaName': regional_admin.vidhan_sabha.name if regional_admin.vidhan_sabha else None,
                    'villageName': regional_admin.village.name if regional_admin.village else '',
                    'panchayatName': regional_admin.panchayat.name if regional_admin.panchayat else None,
                    'listOfPanchayat': list_of_panchayat,
                    'listOfCenters': list_of_centers,
                    'assignedDate': None
                })
            return response
        
        # Teacher
        elif user.role and user.role.role_code == 'TEACHER':
            teacher = Teacher.objects.filter(user=user).first()
            if teacher:
                center_data = None
                if teacher.center:
                    center = teacher.center
                    center_data = {
                        'id': center.id,
                        'centerGuidId': center.center_guid_id,
                        'centerName': center.center_name,
                        'classStatus': center.class_status,
                        'status': center.status,
                        'createdDate': center.created_date,
                        'startedDate': center.started_date,
                        'assignedTeachers': center.assigned_teachers,
                        'assignedRegionalAdmin': center.assigned_regional_admin,
                        'vidhanSabhaId': center.vidhan_sabha_id or 0,
                        'districtId': center.district_id or 0,
                        'panchayatId': center.panchayat_id or 0,
                        'villageId': center.village_id,
                        'totalCenterCount': 0,
                        'regionalAdminName': None,
                        'districtName': None,
                        'vidhanSabhaName': None,
                        'villageName': None,
                        'panchayatName': None,
                        'centerAssignUser': None,
                        'district': None,
                        'vidhanSabha': None,
                        'panchayat': None,
                        'village': None,
                        'totalStudents': None,
                        'teacherName': None,
                        'regionalAdminId': None,
                        'totalActiveStudents': None,
                        'totalPresentStudents': None,
                        'totalAvialableStudents': None,
                        'classStartDate': None,
                        'classEndDate': None,
                        'user': None,
                        'type': 0,
                        'startDate': None,
                        'endDate': None,
                        'reason': None,
                        'noAttendance': None,
                        'endDateWithAttendance': None,
                        'endDateWithNoAttendance': None,
                        'completed': None,
                        'notStarted': None,
                        'classCancelTeacher': None
                    }
                
                response.update({
                    'age': teacher.age,
                    'gender': teacher.gender,
                    'dateOfBirth': teacher.date_of_birth,
                    'contact': teacher.contact,
                    'fullAddress': teacher.full_address,
                    'education': teacher.education,
                    'guardianName': teacher.guardian_name,
                    'guardianNumber': teacher.guardian_number,
                    'count': teacher.count,
                    'assignedTeacherStatus': teacher.assigned_teacher_status,
                    'assignedRegionalAdminStatus': teacher.assigned_regional_admin_status,
                    'enrollmentDate': teacher.enrollment_date,
                    'districtId': teacher.district_id,
                    'vidhanSabhaId': teacher.vidhan_sabha_id,
                    'villageId': teacher.village_id,
                    'panchayatId': teacher.panchayat_id,
                    'centerId': teacher.center_id,
                    'districtName': teacher.district.name if teacher.district else None,
                    'vidhanSabhaName': teacher.vidhan_sabha.name if teacher.vidhan_sabha else None,
                    'villageName': teacher.village.name if teacher.village else None,
                    'panchayatName': teacher.panchayat.name if teacher.panchayat else None,
                    'centerName': teacher.center.center_name if teacher.center else None,
                    'center': center_data,
                    'centerEnrollmentDate': None,
                    'assignedDate': None
                })
            return response
        
        return response
        
    except User.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"UserHelper : GetUserById : {str(e)}")
        raise e


def update_user_device_id(user_id, device_id):
    """Update user device ID"""
    logger.info(f"UserHelper : UpdateDeviceId : Started")
    
    try:
        user = User.objects.filter(id=user_id).first()
        if user:
            user.device_id = device_id
            user.save(update_fields=['device_id'])
            return get_user_by_id(user_id)
        return None
        
    except Exception as e:
        logger.error(f"UserHelper : UpdateDeviceId : {str(e)}")
        raise e

def update_user_password(user_id, new_password):
    """Update user password"""
    logger.info(f"UserHelper : UpdatePassword : Started")
    
    try:
        hashed_password = hash_password(new_password)
        user = User.objects.filter(id=user_id).first()
        if user:
            user.password = hashed_password
            user.save(update_fields=['password'])
            return get_user_by_id(user_id)
        return None
        
    except Exception as e:
        logger.error(f"UserHelper : UpdatePassword : {str(e)}")
        raise e

def get_user_detail_by_phone(phone_number):
    """Get user details by phone number"""
    logger.info(f"UserHelper : GetUserDetailByPhoneNumber : Started")
    
    try:
        user = User.objects.filter(phone_number=phone_number).first()
        if user:
            return {
                "Id": user.id,
                "Name": user.name,
                "PhoneNumber": user.phone_number,
                "Email": user.email,
                "Type": user.role.role_code if user.role else None,
                "Status": user.status
            }
        return None
        
    except Exception as e:
        logger.error(f"UserHelper : GetUserDetailByPhoneNumber : {str(e)}")
        raise e

def search_data(search_type, query_string):
    """Search data by type and query string"""
    logger.info(f"UserHelper : SearchData : Started")
    
    try:
        results = []
        
        search_map = {
            'Users': (User, 'name'),
            'Student': (Student, 'full_name'),
            'District': (District, 'name'),
            'Panchayat': (Panchayat, 'name'),
            'VidhanSabha': (VidhanSabha, 'name'),
            'Village': (Village, 'name'),
            'Center': (Center, 'center_name'),
            'School': (School, 'school_name'),
            'Class': (ClassModel, 'name'),
            'Teacher': (Teacher, 'full_name')
        }
        
        if search_type in search_map:
            model, field = search_map[search_type]
            queryset = model.objects.filter(**{f"{field}__icontains": query_string})[:25]
            results = list(queryset.values())
        
        logger.info(f"UserHelper : SearchData : End")
        return results
        
    except Exception as e:
        logger.error(f"UserHelper : SearchData : {str(e)}")
        raise e

def update_super_admin_user(user_data):
    """Update super admin user - matches .NET logic exactly"""
    logger.info(f"UserHelper : UpdateSuperAdminUser : Started")
    
    try:
        user_id = user_data.get('Id')
        if not user_id:
            logger.error("User ID is required")
            return None
        
        # Get existing user
        try:
            existing_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"User not found with ID: {user_id}")
            return None
        
        # Preserve these fields from existing user (matches .NET logic)
        user_data['EnrolmentRollId'] = existing_user.enrolment_roll_id
        user_data['Password'] = existing_user.password
        user_data['CreatedOn'] = existing_user.created_on
        user_data['Status'] = existing_user.status
        
        # Save the user using the existing save_user function
        saved_user = save_user(user_data)
        
        if saved_user:
            logger.info(f"UserHelper : UpdateSuperAdminUser : End")
            return saved_user
        else:
            return None
        
    except Exception as e:
        logger.error(f"UserHelper : UpdateSuperAdminUser : {str(e)}")
        raise e
#---------------------------------------------------------
# Class APIs Helper Functions
#---------------------------------------------------------

def save_class(class_data, request):
    """Save a new class"""
    logger.info(f"ClassHelper : SaveClass : Started")
    current_user_id = get_user_id_from_token(request)
    
    try:
        class_enrolment_id = class_data.get('classEnrolmentId')
        center_id = class_data.get('centerId')
        today = datetime.now().date()
        
        # Check if class already exists
        check_sql = """
            SELECT Id FROM Class 
            WHERE ClassEnrolmentId = %s 
            AND DATE(StartedDate) = %s 
            AND CenterId = %s
            AND Status = 1
        """
        with connection.cursor() as cursor:
            cursor.execute(check_sql, [class_enrolment_id, today, center_id])
            existing = cursor.fetchone()
            
            if existing:
                return None
            
            # Insert new class - FIX: Added missing Status parameter
            insert_sql = """
                INSERT INTO Class (
                    ClassEnrolmentId, Name, CenterId, UsersId, 
                    TotalStudents, AvilableStudents, StartedDate, 
                    Status, SubStatus, CreatedOn, CreatedBy
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_sql, [
                class_enrolment_id,
                class_data.get('name'),
                center_id,
                class_data.get('userId'),
                class_data.get('totalStudents'),
                class_data.get('avilableStudents'),
                datetime.now(),
                1,  # Active status
                0,   # SubStatus
                datetime.now(),
                current_user_id  # CreatedBy
            ])
            
            # Get the inserted ID
            cursor.execute("SELECT LAST_INSERT_ID()")
            class_id = cursor.fetchone()[0]
            
            # Update center class status
            Center.objects.filter(id=center_id).update(
                class_status=1,  # Active status
                updated_on=datetime.now(),
                updated_by=current_user_id
            )
        
        # Get the saved class
        return get_class_by_id(class_id)
        
    except Exception as e:
        logger.error(f"ClassHelper : SaveClass : {str(e)}")
        raise e

def get_class_by_id(class_id):
    """Get class by ID with soft delete support"""
    try:
        class_obj = ClassModel.objects.filter(id=class_id, status=True).first()
        if class_obj:
            return {
                'Id': class_obj.id,
                'ClassEnrolmentId': class_obj.class_enrolment_id,
                'Name': class_obj.name,
                'CenterId': class_obj.center_id,
                'UsersId': class_obj.users_id,
                'TotalStudents': class_obj.total_students,
                'AvilableStudents': class_obj.avilable_students,
                'StartedDate': class_obj.started_date,
                'EndDate': class_obj.end_date,
                'Status': class_obj.status,
                'SubStatus': class_obj.sub_status,
                'Reason': class_obj.reason,
                'CancelBy': class_obj.cancel_by,
                'CancelDate': class_obj.cancel_date
            }
        return None
    except Exception as e:
        logger.error(f"ClassHelper : get_class_by_id : {str(e)}")
        raise e

def cancel_class(class_data, request=None):
    """Cancel a class"""
    logger.info(f"ClassHelper : CancelClass : Started")
    
    try:
        class_id = class_data.get('id')
        reason = class_data.get('reason')
        cancel_by = class_data.get('cancelBy')
        
        # Get current user ID from token
        current_user_id = None
        if request:
            current_user_id = get_user_id_from_token(request)
        
        class_obj = ClassModel.objects.filter(id=class_id, active_status=True).first()
        if not class_obj:
            return None
        
        current_time = datetime.now()
        class_obj.reason = reason
        class_obj.cancel_by = cancel_by
        class_obj.cancel_date = current_time
        class_obj.status = 3  # Cancel status
        class_obj.updated_on = current_time
        class_obj.updated_by = current_user_id or cancel_by
        class_obj.save()
        
        # Update center class status
        Center.objects.filter(id=class_obj.center_id).update(
            class_status=3,  # Cancel status
            updated_on=current_time,
            updated_by=current_user_id or cancel_by
        )
        
        return get_class_by_id(class_id)
        
    except Exception as e:
        logger.error(f"ClassHelper : CancelClass : {str(e)}")
        raise e

def update_end_class_time(class_id, request=None):
    """Update end class time"""
    logger.info(f"ClassHelper : UpdateEndClassTime : Started")
    
    try:
        # Get current user ID from token
        current_user_id = None
        if request:
            current_user_id = get_user_id_from_token(request)
        
        # First check if class exists
        class_obj = ClassModel.objects.filter(id=class_id, active_status=True).first()
        if not class_obj:
            logger.error(f"Class not found with ID: {class_id}")
            return None
        
        with connection.cursor() as cursor:
            # Get class data
            class_sql = "SELECT CenterId FROM Class WHERE Id = %s AND Status = 1"
            cursor.execute(class_sql, [class_id])
            row = cursor.fetchone()
            
            if not row:
                logger.error(f"Class not found or not active with ID: {class_id}")
                return None
            
            center_id = row[0]
            current_time = datetime.now()
            
            # Update class - set end date and status to completed with updated_by
            update_sql = """
                UPDATE Class 
                SET EndDate = %s, Status = 2, UpdatedOn = %s, UpdatedBy = %s
                WHERE Id = %s AND Status = 1
            """
            cursor.execute(update_sql, [current_time, current_time, current_user_id, class_id])
            
            # Update student active class status
            student_sql = """
                UPDATE Student s
                SET s.ActiveClassStatus = 0, s.UpdatedOn = %s, s.UpdatedBy = %s
                WHERE s.CenterId = %s 
                AND s.Id IN (
                    SELECT DISTINCT sa.StudentId 
                    FROM StudentAttendance sa 
                    WHERE sa.CenterId = %s
                )
            """
            cursor.execute(student_sql, [current_time, current_user_id, center_id, center_id])
            
            # Update center class status to completed
            update_center_sql = """
                UPDATE Center 
                SET ClassStatus = 2, UpdatedOn = %s, UpdatedBy = %s 
                WHERE Id = %s
            """
            cursor.execute(update_center_sql, [current_time, current_user_id, center_id])
        
        # Get the updated class
        return get_class_by_id(class_id)
        
    except Exception as e:
        logger.error(f"ClassHelper : UpdateEndClassTime : {str(e)}")
        raise e
        
    except Exception as e:
        logger.error(f"ClassHelper : UpdateEndClassTime : {str(e)}")
        raise e

def update_class_sub_status(class_id, request=None):
    """Update class sub status"""
    logger.info(f"ClassHelper : UpdateClassSubStatus : Started")
    
    try:
        current_user_id = None
        if request:
            current_user_id = get_user_id_from_token(request)
        
        current_time = datetime.now()
        
        # Check if class exists
        class_obj = ClassModel.objects.filter(id=class_id, active_status=True).first()
        if not class_obj:
            logger.error(f"Class not found with ID: {class_id}")
            return None
        
        # Update using Django ORM
        class_obj.sub_status = 1
        class_obj.updated_on = current_time
        class_obj.updated_by = current_user_id
        class_obj.save()
        
        return get_class_by_id(class_id)
        
    except Exception as e:
        logger.error(f"ClassHelper : UpdateClassSubStatus : {str(e)}")
        raise e

def cancel_class_by_teacher(class_cancel_data, request):
    """Cancel class by teacher"""
    logger.info(f"ClassHelper : CancelClassByTeacher : Started")
    current_user_id = get_user_id_from_token(request)
    
    try:
        # Create new cancel record
        cancel = ClassCancelByTeacher(
            center_id=class_cancel_data.get('CenterId'),
            user_id=class_cancel_data.get('UsersId'),
            starting_date=class_cancel_data.get('StartingDate'),
            ending_date=class_cancel_data.get('EndingDate'),
            reason=class_cancel_data.get('Reason'),
            created_by=current_user_id,
            created_on=datetime.now(),
            status=True
        )
        cancel.save()
        
        # Update class status
        ClassModel.objects.filter(
            center_id=class_cancel_data.get('CenterId'),
            started_date__date=datetime.now().date()
        ).update(
            status=3,  # Cancel status
            updated_on=datetime.now(),
            updated_by=current_user_id
        )
        
        return {'id': cancel.id}
        
    except Exception as e:
        logger.error(f"ClassHelper : CancelClassByTeacher : {str(e)}")
        raise e

def delete_class_by_teacher_id(class_id, request=None):
    """Soft delete class by teacher ID - set active_status to False"""
    logger.info(f"ClassHelper : DeleteClassByTeacherId : Started")
    
    try:
        current_user_id = None
        if request:
            current_user_id = get_user_id_from_token(request)
        
        current_time = datetime.now()
        
        # Get class
        class_obj = ClassModel.objects.filter(id=class_id, active_status=True).first()
        if not class_obj:
            logger.error(f"Class not found with ID: {class_id}")
            return None
        
        # Get users_id from class
        users_id = class_obj.users_id
        
        # Soft delete - set active_status to False
        class_obj.active_status = False
        class_obj.updated_on = current_time
        class_obj.updated_by = current_user_id
        class_obj.save()
        
        # Soft delete class cancel by teacher
        ClassCancelByTeacher.objects.filter(user_id=users_id, status=True).update(
            status=False,
            updated_on=current_time,
            updated_by=current_user_id
        )
        
        # Soft delete student attendance
        StudentAttendance.objects.filter(class_obj_id=class_id, status=True).update(
            status=False,
            updated_on=current_time,
            updated_by=current_user_id
        )
        
        logger.info(f"ClassHelper : DeleteClassByTeacherId : End")
        return {'id': class_id, 'deleted': True}
        
    except Exception as e:
        logger.error(f"ClassHelper : DeleteClassByTeacherId : {str(e)}")
        raise e

def get_class_current_status(center_id, teacher_id):
    """Get class current status"""
    logger.info(f"ClassHelper : GetClassCurrentStatus : Started")
    
    try:
        today = datetime.now().date()
        result = {'data': [], 'status': True}
        
        # Check holidays
        holidays = Holidays.objects.filter(
            center_id=center_id,
            start_date__date__lte=today,
            end_date__date__gte=today,
            status=True
        )
        
        for h in holidays:
            result['data'].append({
                'name': h.name,
                'type': 1,
                'startedDate': h.start_date,
                'endDate': h.end_date
            })
        
        # Check class cancel by teacher
        cancels = ClassCancelByTeacher.objects.filter(
            user_id=teacher_id,
            starting_date__date__lte=today,
            ending_date__date__gte=today,
            status=True
        )
        
        for c in cancels:
            result['data'].append({
                'name': c.reason,
                'type': 2,
                'startedDate': c.starting_date,
                'endDate': c.ending_date
            })
        
        # Check active class
        active_class = ClassModel.objects.filter(
            started_date__date=today,
            center_id=center_id,
            status=True
        ).first()
        
        if active_class:
            result['data'].append({
                'name': 'Class is going on',
                'type': 3,
                'subStatus': active_class.sub_status,
                'id': active_class.id,
                'startedDate': active_class.started_date,
                'endDate': active_class.end_date
            })
        
        # Check completed class
        completed_class = ClassModel.objects.filter(
            started_date__date=today,
            center_id=center_id,
            status=2
        ).first()
        
        if completed_class:
            result['data'].append({
                'name': 'Class Ended',
                'type': 4,
                'id': completed_class.id,
                'startedDate': completed_class.started_date,
                'endDate': completed_class.end_date
            })
        
        return result
        
    except Exception as e:
        logger.error(f"ClassHelper : GetClassCurrentStatus : {str(e)}")
        raise e

def get_live_class_detail(class_id):
    """Get live class detail"""
    logger.info(f"ClassHelper : GetLiveClassDetail : Started")
    
    try:
        today = datetime.now().date()
        sql = """
            SELECT 
                Id, Name, Status, StartedDate as StartDate,
                EndDate, TotalStudents, AvilableStudents, SubStatus
            FROM Class
            WHERE DATE(StartedDate) = %s AND Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [today, class_id])
            row = cursor.fetchone()
            
            if row:
                columns = [col[0] for col in cursor.description]
                row_dict = dict(zip(columns, row))
                # Convert PascalCase to camelCase to match serializer
                return {
                    'id': row_dict.get('Id'),
                    'name': row_dict.get('Name'),
                    'status': row_dict.get('Status'),
                    'startDate': row_dict.get('StartDate'),
                    'endDate': row_dict.get('EndDate'),
                    'totalStudents': row_dict.get('TotalStudents'),
                    'avilableStudents': row_dict.get('AvilableStudents'),
                    'subStatus': row_dict.get('SubStatus')
                }
        
        return None
        
    except Exception as e:
        logger.error(f"ClassHelper : GetLiveClassDetail : {str(e)}")
        raise e


#---------------------------------------------------------
# District APIs Helper Functions
#---------------------------------------------------------

def get_all_districts(offset, limit):
    """Get all districts with pagination"""
    logger.info(f"DistrictHelper : GetAllDistrict : Started")
    
    try:
        queryset = District.objects.filter(status=True).order_by('id')
        
        if offset > 0 or limit > 0:
            queryset = queryset[offset:offset + limit]
        
        result = []
        for d in queryset:
            result.append({
                'Id': d.id,
                'DistrictGuidId': d.district_guid_id,
                'Name': d.name,
                'Status': d.status,
                'CreatedOn': d.created_on,
                'CreatedBy': d.created_by
            })
        return result
                
    except Exception as e:
        logger.error(f"DistrictHelper : GetAllDistrict : {str(e)}")
        raise e

def save_district(district_data):
    """Save or update district"""
    logger.info(f"DistrictHelper : SaveDistrict : Started")
    
    try:
        district_id = int(district_data.get('Id', 0))
        
        if district_id > 0:
            # Update existing district - NEVER update DistrictGuidId
            try:
                district = District.objects.get(id=district_id)
                
                # Update fields
                if 'Name' in district_data and district_data['Name'] is not None:
                    district.name = district_data['Name']
                if 'Status' in district_data and district_data['Status'] is not None:
                    district.status = district_data['Status']
                if 'CreatedBy' in district_data and district_data['CreatedBy'] is not None:
                    district.created_by = district_data['CreatedBy']
                
                # Always update timestamps
                district.updated_on = datetime.now()
                updated_by = district_data.get('UpdatedBy') or district_data.get('CreatedBy')
                if updated_by:
                    district.updated_by = updated_by
                
                district.save()
                
            except District.DoesNotExist:
                logger.error(f"District not found with ID: {district_id}")
                return None
        else:
            # Insert new district
            district_guid = str(uuid.uuid4())
            
            district = District(
                district_guid_id=district_guid,
                name=district_data.get('Name'),
                status=district_data.get('Status'),
                created_on=datetime.now(),
                created_by=district_data.get('CreatedBy')
            )
            district.save()
            district_id = district.id
        
        # Get the saved district
        return get_district_by_id(district_id)
        
    except Exception as e:
        logger.error(f"DistrictHelper : SaveDistrict : {str(e)}")
        raise e

def get_district_by_id(district_id):
    """Get district by ID"""
    try:
        district = District.objects.filter(id=district_id, status=True).first()
        if district:
            return {
                'Id': district.id,
                'DistrictGuidId': district.district_guid_id,
                'Name': district.name,
                'Status': district.status,
                'CreatedOn': district.created_on,
                'CreatedBy': district.created_by
            }
        return None
    except Exception as e:
        logger.error(f"DistrictHelper : get_district_by_id : {str(e)}")
        raise e

def check_district_name(name):
    """Check if district name exists"""
    logger.info(f"DistrictHelper : CheckDistrictName : Started")
    
    try:
        return District.objects.filter(name=name).values_list('name', flat=True).first()
    except Exception as e:
        logger.error(f"DistrictHelper : CheckDistrictName : {str(e)}")
        raise e

#---------------------------------------------------------

#---------------------------------------------------------
# Dashboard APIs Helper Functions
#---------------------------------------------------------

def get_class_count_by_month(center_id, start_date, end_date):
    """Get class count by month for a center"""
    logger.info(f"DashboardHelper : GetClassCountByMonth : Started")
    
    try:
        start = start_date.date()
        end = end_date.date()
        
        class_count = ClassModel.objects.filter(
            center_id=center_id,
            started_date__date__gte=start,
            end_date__date__lte=end,
            status=True
        ).count()
            
        holiday_count = Holidays.objects.filter(
            center_id=center_id,
            start_date__date__gte=start,
            end_date__date__gte=start,
            status=True
        ).count()
        
        cancel_count = ClassCancelByTeacher.objects.filter(
            center_id=center_id,
            starting_date__date__gte=start,
            ending_date__date__gte=start,
            status=True
        ).count()
        
        result = {
            "status": True,
            "data": [
                {
                    "holidayCount": holiday_count,
                    "classCount": class_count,
                    "classCancelTeacherCount": cancel_count
                }
            ]
        }
        
        return result
        
    except Exception as e:
        logger.error(f"DashboardHelper : GetClassCountByMonth : {str(e)}")
        raise e

def get_total_gender_ratio_by_center_id(center_id, start_date, end_date):
    """Get total gender ratio by center ID - matches C# logic exactly"""
    logger.info(f"DashboardHelper : GetTotalGenderRatioByCenterId : Started")
    
    try:
        result = {
            "Status": True,
            "Data": []
        }
        
        with connection.cursor() as cursor:
            # Get total students WITH date filter (matches C# exactly)
            # C#: .Where(x => x.CenterId == centerId && x.CreatedOn.Value.Date >= startDate.Date && x.CreatedOn.Value.Date <= endDate.Date)
            total_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s 
                AND DATE(CreatedOn) >= %s 
                AND DATE(CreatedOn) <= %s
            """
            cursor.execute(total_sql, [center_id, start_date.date(), end_date.date()])
            total_students = cursor.fetchone()[0] or 0
            
            # Get female students WITH date filter (matches C# exactly)
            # C#: .Where(x => x.CenterId == centerId && x.Gender == "FeMale" && x.CreatedOn.Value.Date >= startDate.Date && x.CreatedOn.Value.Date <= endDate.Date)
            female_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s 
                AND Gender = 'FeMale'
                AND DATE(CreatedOn) >= %s 
                AND DATE(CreatedOn) <= %s
            """
            cursor.execute(female_sql, [center_id, start_date.date(), end_date.date()])
            female_count = cursor.fetchone()[0] or 0
            
            # Get male students (from total students list which already has date filter)
            # C#: int MaleCount = TotalStudents.Where(x => x.Gender == "Male").ToList().Count();
            # Since we already have total_students and female_count, we can calculate male_count
            male_count = total_students - female_count
            
            result["Data"].append({
                "FeMaleCount": female_count,
                "MaleCount": male_count,
                "TotalStudentCount": total_students
            })
            
            logger.info(f"DashboardHelper : GetTotalGenderRatioByCenterId : End")
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalGenderRatioByCenterId : {str(e)}")
        raise e

def get_total_student_of_class(center_id, start_date, end_date):
    """Get total student of class by center"""
    logger.info(f"DashboardHelper : GetTotalStudentOfClass : Started")
    
    list_of_existing_grade = ["UKG", "LKG", "Pre Nursery", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"]
    
    try:
        with connection.cursor() as cursor:
            # Get students grouped by grade
            student_sql = """
                SELECT 
                    Grade,
                    COUNT(*) as Total,
                    SUM(CASE WHEN Gender = 'FeMale' THEN 1 ELSE 0 END) as FeMaleCount,
                    SUM(CASE WHEN Gender = 'Male' THEN 1 ELSE 0 END) as MaleCount
                FROM Student
                WHERE CenterId = %s 
                AND DATE(CreatedOn) >= %s 
                AND DATE(CreatedOn) <= %s
                GROUP BY Grade
                ORDER BY Grade
            """
            cursor.execute(student_sql, [center_id, start_date.date(), end_date.date()])
            rows = cursor.fetchall()
            
            # Get total students
            total_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s
            """
            cursor.execute(total_sql, [center_id])
            total_students = cursor.fetchone()[0] or 0
            
            result = {
                "Status": True,
                "TotalStudents": total_students,
                "Data": []
            }
            
            grade_list = []
            for row in rows:
                grade = row[0]
                grade_list.append(grade)
                result["Gata"].append({
                    "Grade": grade,
                    "FeMaleCount": row[2] or 0,
                    "MaleCount": row[3] or 0,
                    "TotalStudentCount": row[1] or 0
                })
            
            # If no data, add all grades with 0
            if len(rows) == 0:
                for grade in list_of_existing_grade:
                    result["Data"].append({
                        "Grade": grade,
                        "FeMaleCount": 0,
                        "MaleCount": 0,
                        "TotalStudentCount": 0
                    })
            else:
                # Add missing grades with 0
                list_not_in_db = [g for g in list_of_existing_grade if g not in grade_list]
                for grade in list_not_in_db:
                    result["Data"].append({
                        "Grade": grade,
                        "FeMaleCount": 0,
                        "MaleCount": 0,
                        "TotalStudentCount": 0
                    })
            
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalStudentOfClass : {str(e)}")
        raise e

def get_center_detail_by_month(center_id, month, year):
    """Get center detail by month and year"""
    logger.info(f"DashboardHelper : GetCenterDetailByMonth : Started")
    
    try:
        start_date = datetime(year, month, 1)
        end_date = start_date.replace(day=1, month=start_date.month + 1) - timedelta(days=1)
        
        result = {
            "status": True,
            "data": []
        }
        
        with connection.cursor() as cursor:
            i = 0
            current_date = start_date
            
            while current_date <= end_date:
                data = {
                    "date": current_date.strftime('%Y-%m-%d'),
                    "type": i + 1,
                    "detail": []
                }
                
                if i == 0:
                    data["detail"].append({
                        "class": "Class1",
                        "classId": 1,
                        "startedDate": "2023-11-20",
                        "endDate": "2023-11-20",
                        "totalStudent": 25
                    })
                elif i == 1:
                    data["detail"].append({
                        "holidayName": "Holiday",
                        "startDate": "2023-11-20",
                        "endDate": "2023-11-20"
                    })
                elif i == 2:
                    data["detail"].append({
                        "classCancelBy": "Cancel by teacher",
                        "reason": "Cancel by teacher",
                        "startingDate": "2023-11-20",
                        "endingDate": "2023-11-20"
                    })
                elif i == 3:
                    data["detail"].append({
                        "reason": "Center deactivate",
                        "cancelBy": "Cancel by admin"
                    })
                else:
                    data["detail"].append({
                        "reason": "Upcoming"
                    })
                
                result["data"].append(data)
                current_date += timedelta(days=1)
                i += 1
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"DashboardHelper : GetCenterDetailByMonth : {str(e)}")
        raise e

def get_total_bpl(center_id, start_date, end_date):
    """Get total BPL students by center"""
    logger.info(f"DashboardHelper : GetTotalBpl : Started")
    
    try:
        start = start_date.date()
        end = end_date.date()
        
        # Get total BPL students
        bpl_count = Student.objects.filter(
            center_id=center_id,
            bpl=True,
            created_on__date__gte=start,
            created_on__date__lte=end,
            status=True
        ).count()
        
        # Get female BPL students
        female_count = Student.objects.filter(
            center_id=center_id,
            bpl=True,
            gender='FeMale',
            created_on__date__gte=start,
            created_on__date__lte=end,
            status=True
        ).count()
        
        # Get male BPL students
        male_count = Student.objects.filter(
            center_id=center_id,
            bpl=True,
            gender='Male',
            created_on__date__gte=start,
            created_on__date__lte=end,
            status=True
        ).count()
        
        # Get total students
        total_students = Student.objects.filter(
            center_id=center_id,
            status=True
        ).count()
        
        result = {
            "Status": True,
            "TotalStudents": total_students,
            "Data": [
                {
                    "FeMaleCount": female_count,
                    "MaleCount": male_count,
                    "TotalBplStudents": bpl_count
                }
            ]
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalBpl : {str(e)}")
        raise e

def get_total_student_category_of_class(center_id, start_date, end_date):
    """Get total student category of class"""
    logger.info(f"DashboardHelper : GetTotalStudentCategoryOfClass : Started")
    
    categories = ["General", "OBC", "SC", "ST", "EWS", "Others"]
    
    try:
        with connection.cursor() as cursor:
            # Get students grouped by category
            category_sql = """
                SELECT 
                    Category,
                    COUNT(*) as Total
                FROM Student
                WHERE CenterId = %s 
                AND DATE(CreatedOn) >= %s 
                AND DATE(CreatedOn) <= %s
                GROUP BY Category
                ORDER BY Category
            """
            cursor.execute(category_sql, [center_id, start_date.date(), end_date.date()])
            rows = cursor.fetchall()
            
            # Create dict for quick lookup
            category_dict = {}
            for row in rows:
                category_dict[row[0]] = row[1]
            
            # Get total students
            total_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s
            """
            cursor.execute(total_sql, [center_id])
            total_students = cursor.fetchone()[0] or 0
            
            result = {
                "Status": True,
                "TotalStudents": total_students,
                "Data": []
            }
            
            for category in categories:
                result["Data"].append({
                    "Category": category,
                    "TotalStudentCount": category_dict.get(category, 0)
                })
            
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalStudentCategoryOfClass : {str(e)}")
        raise e

def get_user_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get user by filter"""
    logger.info(f"DashboardHelper : GetUserByFilter : Started")
    
    try:
        with connection.cursor() as cursor:
            # Build WHERE clause
            where_conditions = [
                "DATE(CreatedOn) >= %s",
                "DATE(CreatedOn) <= %s",
                "DistrictId = %s"
            ]
            params = [start_date.date(), end_date.date(), district_id]
            
            if vidhan_sabha_id:
                where_conditions.append("(VidhanSabhaId IS NULL OR VidhanSabhaId = %s)")
                params.append(vidhan_sabha_id)
            if panchayta_id:
                where_conditions.append("(PanchayatId IS NULL OR PanchayatId = %s)")
                params.append(panchayta_id)
            if village_id:
                where_conditions.append("(VillageId IS NULL OR VillageId = %s)")
                params.append(village_id)
            
            where_clause = " AND ".join(where_conditions)
            
            # Get users count
            user_sql = f"""
                SELECT COUNT(*) 
                FROM Users 
                WHERE {where_clause}
            """
            cursor.execute(user_sql, params)
            user_count = cursor.fetchone()[0] or 0
            
            # Get centers count
            center_where = where_clause.replace("DATE(CreatedOn)", "DATE(StartedDate)")
            center_sql = f"""
                SELECT COUNT(*) 
                FROM Center 
                WHERE {center_where}
            """
            cursor.execute(center_sql, params)
            center_count = cursor.fetchone()[0] or 0
            
            result = {
                "status": True,
                "teacherCount": user_count,
                "centerCount": center_count
            }
            
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetUserByFilter : {str(e)}")
        raise e

def get_total_bpl_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get total BPL by filter"""
    logger.info("DashboardHelper : GetTotalBplByFilter : Started")

    try:
        with connection.cursor() as cursor:

            # -----------------------------
            # BPL WHERE CLAUSE
            # -----------------------------
            where_conditions = [
                "DATE(CreatedOn) >= %s",
                "DATE(CreatedOn) <= %s",
                "Bpl = 1",
                "DistrictId = %s"
            ]

            params = [
                start_date.date(),
                end_date.date(),
                district_id
            ]

            if vidhan_sabha_id:
                where_conditions.append("(VidhanSabhaId IS NULL OR VidhanSabhaId = %s)")
                params.append(vidhan_sabha_id)

            if panchayta_id:
                where_conditions.append("(PanchayatId IS NULL OR PanchayatId = %s)")
                params.append(panchayta_id)

            if village_id:
                where_conditions.append("(VillageId IS NULL OR VillageId = %s)")
                params.append(village_id)

            where_clause = " AND ".join(where_conditions)

            # -----------------------------
            # Total BPL Students
            # -----------------------------
            bpl_sql = f"""
                SELECT COUNT(*)
                FROM Student
                WHERE {where_clause}
            """
            cursor.execute(bpl_sql, params)
            bpl_count = cursor.fetchone()[0] or 0

            # -----------------------------
            # Female BPL Students
            # -----------------------------
            female_sql = f"""
                SELECT COUNT(*)
                FROM Student
                WHERE {where_clause}
                AND Gender = 'FeMale'
            """
            cursor.execute(female_sql, params)
            female_count = cursor.fetchone()[0] or 0

            # -----------------------------
            # Male BPL Students
            # -----------------------------
            male_sql = f"""
                SELECT COUNT(*)
                FROM Student
                WHERE {where_clause}
                AND Gender = 'Male'
            """
            cursor.execute(male_sql, params)
            male_count = cursor.fetchone()[0] or 0

            # -----------------------------
            # Total Students (Without BPL Filter)
            # -----------------------------
            total_where_conditions = [
                "DATE(CreatedOn) >= %s",
                "DATE(CreatedOn) <= %s",
                "DistrictId = %s"
            ]

            total_params = [
                start_date.date(),
                end_date.date(),
                district_id
            ]

            if vidhan_sabha_id:
                total_where_conditions.append("(VidhanSabhaId IS NULL OR VidhanSabhaId = %s)")
                total_params.append(vidhan_sabha_id)

            if panchayta_id:
                total_where_conditions.append("(PanchayatId IS NULL OR PanchayatId = %s)")
                total_params.append(panchayta_id)

            if village_id:
                total_where_conditions.append("(VillageId IS NULL OR VillageId = %s)")
                total_params.append(village_id)

            total_where_clause = " AND ".join(total_where_conditions)

            total_sql = f"""
                SELECT COUNT(*)
                FROM Student
                WHERE {total_where_clause}
            """

            cursor.execute(total_sql, total_params)
            total_students = cursor.fetchone()[0] or 0

            result = {
                "Status": True,
                "TotalStudents": total_students,
                "Data": [
                    {
                        "FeMaleCount": female_count,
                        "MaleCount": male_count,
                        "TotalBplStudents": bpl_count
                    }
                ]
            }

            return json.dumps(result)

    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalBplByFilter : {str(e)}")
        raise e

def get_total_gender_ratio_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get total gender ratio by filter - matches C# logic exactly"""
    logger.info(f"DashboardHelper : GetTotalGenderRatioByFilter : Started")
    
    try:
        with connection.cursor() as cursor:
            # Build WHERE clause
            where_conditions = [
                "DATE(CreatedOn) >= %s",
                "DATE(CreatedOn) <= %s",
                "DistrictId = %s"
            ]
            params = [start_date.date(), end_date.date(), district_id]
            
            if vidhan_sabha_id:
                where_conditions.append("(VidhanSabhaId IS NULL OR VidhanSabhaId = %s)")
                params.append(vidhan_sabha_id)
            if panchayta_id:
                where_conditions.append("(PanchayatId IS NULL OR PanchayatId = %s)")
                params.append(panchayta_id)
            if village_id:
                where_conditions.append("(VillageId IS NULL OR VillageId = %s)")
                params.append(village_id)
            
            where_clause = " AND ".join(where_conditions)
            
            #Query 1: Get ALL students (with all filters) - matches C# TotalStudents
            # C#: List<Student> TotalStudents = appDbContext.Student.Where(x => ...).ToList();
            total_students_sql = f"""
                SELECT 
                    Id,
                    Gender
                FROM Student 
                WHERE {where_clause}
            """
            cursor.execute(total_students_sql, params)
            total_rows = cursor.fetchall()
            
            # Total count
            total_students = len(total_rows)
            
            # Male count from TotalStudents list (matches C# exactly)
            # C#: int MaleCount = TotalStudents.Where(x => x.Gender == "Male").Count();
            male_count = sum(1 for row in total_rows if row[1] == 'Male')
            
            #Query 2: Get Female students only (with all filters) - matches C# FeMaleStudents
            # C#: List<Student> FeMaleStudents = appDbContext.Student.Where(x => x.Gender == "FeMale" && ...).ToList();
            female_sql = f"""
                SELECT COUNT(*) 
                FROM Student 
                WHERE {where_clause} AND Gender = 'FeMale'
            """
            cursor.execute(female_sql, params)
            female_count = cursor.fetchone()[0] or 0
            
            result = {
                "Status": True,
                "Data": [
                    {
                        "FeMaleCount": female_count,
                        "MaleCount": male_count,
                        "TotalStudentCount": total_students
                    }
                ]
            }
            
            logger.info(f"DashboardHelper : GetTotalGenderRatioByFilter : End")
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalGenderRatioByFilter : {str(e)}")
        raise e

def get_total_student_category_of_class_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    logger.info(f"DashboardHelper : GetTotalStudentCategoryOfClassByFilter : Started")
    
    # Match C# exactly - ST NOT in list (even though it's in switch case)
    categories = ["General", "OBC", "SC", "EWS", "Others"]
    
    try:
        with connection.cursor() as cursor:
            # Build WHERE clause
            where_conditions = [
                "DATE(CreatedOn) >= %s",
                "DATE(CreatedOn) <= %s",
                "DistrictId = %s"
            ]
            params = [start_date.date(), end_date.date(), district_id]
            
            if vidhan_sabha_id:
                where_conditions.append("(VidhanSabhaId IS NULL OR VidhanSabhaId = %s)")
                params.append(vidhan_sabha_id)
            if panchayta_id:
                where_conditions.append("(PanchayatId IS NULL OR PanchayatId = %s)")
                params.append(panchayta_id)
            if village_id:
                where_conditions.append("(VillageId IS NULL OR VillageId = %s)")
                params.append(village_id)
            
            where_clause = " AND ".join(where_conditions)
            
            category_sql = f"""
                SELECT 
                    Category,
                    COUNT(*) as Total
                FROM Student
                WHERE {where_clause}
                GROUP BY Category
                ORDER BY Category
            """
            cursor.execute(category_sql, params)
            rows = cursor.fetchall()
            
            category_dict = {}
            for row in rows:
                category_dict[row[0]] = row[1]
            
            result = {
                "Status": True,  # PascalCase to match C#
                "Data": []       # PascalCase to match C#
            }
            
            for category in categories:
                result["Data"].append({
                    "Category": category,              # PascalCase
                    "TotalStudentCount": category_dict.get(category, 0)  # PascalCase
                })
            
            logger.info(f"DashboardHelper : GetTotalStudentCategoryOfClassByFilter : End")
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalStudentCategoryOfClassByFilter : {str(e)}")
        raise e

def get_total_student_grade_of_class_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get total student grade of class by filter"""
    logger.info(f"DashboardHelper : GetTotalStudenGradetOfClassByFilter : Started")
    
    try:
        with connection.cursor() as cursor:
            # Build WHERE clause
            where_conditions = [
                "DATE(CreatedOn) >= %s",
                "DATE(CreatedOn) <= %s",
                "DistrictId = %s"
            ]
            params = [start_date.date(), end_date.date(), district_id]
            
            if vidhan_sabha_id:
                where_conditions.append("(VidhanSabhaId IS NULL OR VidhanSabhaId = %s)")
                params.append(vidhan_sabha_id)
            if panchayta_id:
                where_conditions.append("(PanchayatId IS NULL OR PanchayatId = %s)")
                params.append(panchayta_id)
            if village_id:
                where_conditions.append("(VillageId IS NULL OR VillageId = %s)")
                params.append(village_id)
            
            where_clause = " AND ".join(where_conditions)
            
            # Get students grouped by grade
            grade_sql = f"""
                SELECT 
                    Grade,
                    COUNT(*) as Total,
                    SUM(CASE WHEN Gender = 'FeMale' THEN 1 ELSE 0 END) as FeMaleCount,
                    SUM(CASE WHEN Gender = 'Male' THEN 1 ELSE 0 END) as MaleCount
                FROM Student
                WHERE {where_clause}
                GROUP BY Grade
                ORDER BY Grade
            """
            cursor.execute(grade_sql, params)
            rows = cursor.fetchall()
            
            result = {
                "status": True,
                "data": []
            }
            
            for row in rows:
                result["data"].append({
                    "grade": row[0],
                    "feMaleCount": row[2] or 0,
                    "maleCount": row[3] or 0,
                    "totalStudentCount": row[1] or 0
                })
            
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalStudenGradetOfClassByFilter : {str(e)}")
        raise e

def get_district_of_center_by_filter(district_id, vidhan_sabha_id, start_date, end_date):
    """Get district of center by filter"""
    logger.info(f"DashboardHelper : GetDistrictOfCenterByFilter : Started")
    
    try:
        with connection.cursor() as cursor:
            # Get total centers
            total_sql = """
                SELECT COUNT(*) 
                FROM Center 
                WHERE DATE(StartedDate) >= %s 
                AND DATE(StartedDate) <= %s
            """
            cursor.execute(total_sql, [start_date.date(), end_date.date()])
            total_centers = cursor.fetchone()[0] or 0
            
            result = {
                "status": True,
                "totalCenters": total_centers,
                "data": []
            }
            
            if district_id == 0 and vidhan_sabha_id == 0:
                # Get centers grouped by district
                center_sql = """
                    SELECT 
                        DistrictId,
                        COUNT(*) as TotalCenterCount
                    FROM Center
                    WHERE DATE(StartedDate) >= %s 
                    AND DATE(StartedDate) <= %s
                    GROUP BY DistrictId
                    ORDER BY DistrictId
                """
                cursor.execute(center_sql, [start_date.date(), end_date.date()])
                rows = cursor.fetchall()
                
                # Get districts
                district_sql = "SELECT Id, Name FROM District"
                cursor.execute(district_sql)
                districts = cursor.fetchall()
                district_dict = {d[0]: d[1] for d in districts}
                
                for row in rows:
                    result["data"].append({
                        "districtId": row[0],
                        "districtName": district_dict.get(row[0]),
                        "totalCenterCount": row[1]
                    })
                    
            elif district_id != 0 and vidhan_sabha_id != 0:
                # Get centers by district and vidhan sabha
                center_sql = """
                    SELECT COUNT(*) 
                    FROM Center 
                    WHERE DistrictId = %s 
                    AND VidhanSabhaId = %s
                    AND DATE(StartedDate) >= %s 
                    AND DATE(StartedDate) <= %s
                """
                cursor.execute(center_sql, [district_id, vidhan_sabha_id, start_date.date(), end_date.date()])
                center_count = cursor.fetchone()[0] or 0
                
                # Get district name
                dist_sql = "SELECT Name FROM District WHERE Id = %s"
                cursor.execute(dist_sql, [district_id])
                dist_row = cursor.fetchone()
                district_name = dist_row[0] if dist_row else None
                
                result["totalCenterCount"] = center_count
                result["districtName"] = district_name
                result["vidhanSabhaName"] = district_name
                result["districtId"] = district_id
                result["vidhanSabhaId"] = vidhan_sabha_id
                
            elif district_id != 0:
                # Get centers by district
                center_sql = """
                    SELECT 
                        COUNT(*) as TotalCenterCount
                    FROM Center 
                    WHERE DistrictId = %s 
                    AND DATE(StartedDate) >= %s 
                    AND DATE(StartedDate) <= %s
                """
                cursor.execute(center_sql, [district_id, start_date.date(), end_date.date()])
                row = cursor.fetchone()
                
                if row:
                    # Get district name
                    dist_sql = "SELECT Name FROM District WHERE Id = %s"
                    cursor.execute(dist_sql, [district_id])
                    dist_row = cursor.fetchone()
                    district_name = dist_row[0] if dist_row else None
                    
                    result["data"].append({
                        "districtName": district_name,
                        "districtId": district_id,
                        "totalCenterCount": row[0] or 0
                    })
            
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetDistrictOfCenterByFilter : {str(e)}")
        raise e

def get_student_attendance_by_percentage():
    """Get student attendance by percentage"""
    logger.info(f"DashboardHelper : GetStudentAttendanceByPercentage : Started")
    
    try:
        result = {
            "Data": [
                {
                    "TenPercentage": 10,
                    "TwentyPercentage": 20,
                    "ThrityPercentage": 30,
                    "FourtyPercentage": 40,
                    "FiftyPercentage": 50,
                    "SixtyPercentage": 60,
                    "SeventyPercentage": 70,
                    "EightyPercentage": 80,
                    "NintyPercentage": 90,
                    "HunderedPercentage": 100
                }
            ],
            "TotalStudent": 100
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"DashboardHelper : GetStudentAttendanceByPercentage : {str(e)}")
        raise e

#---------------------------------------------------------
# Holidays APIs Helper Functions
#---------------------------------------------------------

def save_holidays(holidays_data):
    """Save or update holidays"""
    logger.info(f"HolidaysHelper : SaveHolidays : Started")
    
    try:
        holiday_id = holidays_data.get('Id', 0)
        list_center_ids = holidays_data.get('ListCenterIds', '')
        
        # Parse center IDs from comma-separated string
        center_ids = []
        if list_center_ids and isinstance(list_center_ids, str):
            center_ids = [int(x.strip()) for x in list_center_ids.split(',') if x.strip()]
        elif isinstance(list_center_ids, list):
            center_ids = [int(x) for x in list_center_ids if x]
        elif list_center_ids:
            center_ids = [int(list_center_ids)]
        
        if not center_ids:
            logger.error("No valid center IDs provided")
            return None
        
        # Get values
        start_date = holidays_data.get('StartDate')
        end_date = holidays_data.get('EndDate')
        name = holidays_data.get('Name')
        description = holidays_data.get('Description')
        status = holidays_data.get('Status')
        created_by = holidays_data.get('CreatedBy')
        created_on = holidays_data.get('CreatedOn') or datetime.now()
        
        if holiday_id > 0:
            # Get existing holidays with same name
            existing_holidays = Holidays.objects.filter(name=name, status=True)
            existing_center_ids = list(existing_holidays.values_list('center_id', flat=True))
            
            # Remove holidays that are not in the new list - soft delete
            center_ids_to_remove = [cid for cid in existing_center_ids if cid not in center_ids]
            if center_ids_to_remove:
                Holidays.objects.filter(name=name, center_id__in=center_ids_to_remove).update(
                    status=False,
                    updated_on=datetime.now(),
                    updated_by=created_by
                )
            
            # Add new holidays
            center_ids_to_add = [cid for cid in center_ids if cid not in existing_center_ids]
            for center_id in center_ids_to_add:
                Holidays.objects.create(
                    start_date=start_date,
                    end_date=end_date,
                    name=name,
                    description=description,
                    status=status,
                    center_id=center_id,
                    created_on=created_on,
                    created_by=created_by
                )
            
            # Update existing holidays
            for center_id in existing_center_ids:
                if center_id in center_ids:
                    Holidays.objects.filter(name=name, center_id=center_id).update(
                        start_date=start_date,
                        end_date=end_date,
                        name=name,
                        description=description,
                        status=status,
                        updated_on=datetime.now()
                    )
        else:
            # Insert new holidays
            for center_id in center_ids:
                Holidays.objects.create(
                    start_date=start_date,
                    end_date=end_date,
                    name=name,
                    description=description,
                    status=status,
                    center_id=center_id,
                    created_on=created_on,
                    created_by=created_by
                )
        
        logger.info(f"HolidaysHelper : SaveHolidays : End")
        return {'status': True, 'message': 'Holidays saved successfully'}
        
    except Exception as e:
        logger.error(f"HolidaysHelper : SaveHolidays : {str(e)}")
        raise e
    
def get_all_holidays_by_teacher_id(teacher_id):
    """Get all holidays by teacher ID"""
    logger.info(f"HolidaysHelper : GetAllHolidaysByTeacherId : Started")
    
    try:
        today = datetime.now().date()
        holidays = Holidays.objects.filter(
            center__assigned_teachers=teacher_id,
            start_date__date__gte=today,
            end_date__date__lte=today,
            status=True
        ).select_related('center')
        
        result = []
        for h in holidays:
            result.append({
                'Id': h.id,
                'Name': h.name,
                'CenterId': h.center_id,
                'Description': h.description
            })
        return result
            
    except Exception as e:
        logger.error(f"HolidaysHelper : GetAllHolidaysByTeacherId : {str(e)}")
        raise e

def get_all_holidays_by_year(year):
    """Get all holidays by year"""
    logger.info(f"HolidaysHelper : GetAllHolidaysByYear : Started")
    
    try:
        holidays = Holidays.objects.filter(start_date__year=year).select_related('center')
        result = []
        for h in holidays:
            result.append({
                'Id': h.id,
                'Name': h.name,
                'Description': h.description,
                'Status': h.status,
                'StartDate': h.start_date,
                'EndDate': h.end_date,
                'CenterId': h.center_id,
                'CreatedOn': h.created_on,
                'CreatedBy': h.created_by
            })
        return result
            
    except Exception as e:
        logger.error(f"HolidaysHelper : GetAllHolidaysByYear : {str(e)}")
        raise e

def get_all_holidays_by_center_id(center_id):
    """Get all holidays by center ID"""
    logger.info(f"HolidaysHelper : GetAllHolidaysByCenterId : Started")
    
    try:
        holidays = Holidays.objects.filter(center_id=center_id).select_related('center')
        result = []
        for h in holidays:
            result.append({
                'Id': h.id,
                'Name': h.name,
                'Description': h.description,
                'Status': h.status,
                'StartDate': h.start_date,
                'EndDate': h.end_date,
                'CenterId': h.center_id,
                'CreatedOn': h.created_on,
                'CreatedBy': h.created_by
            })
        return result
            
    except Exception as e:
        logger.error(f"HolidaysHelper : GetAllHolidaysByCenterId : {str(e)}")
        raise e

def get_all_holidays(status, user_id=0):
    """Get all holidays with optional status and user filter"""
    logger.info(f"HolidaysHelper : GetAllHolidays : Started")
    
    try:
        today = datetime.now().date()
        result = []
        
        if user_id == 0:
            # SuperAdmin - get all holidays
            queryset = Holidays.objects.select_related('center').order_by('start_date')
            if status != 1:
                # Upcoming holidays
                queryset = queryset.filter(start_date__date__gte=today)
        else:
            # Regional Admin - filter by created_by
            queryset = Holidays.objects.filter(created_by=user_id).select_related('center').order_by('start_date')
            if status != 1:
                # Upcoming holidays
                queryset = queryset.filter(start_date__date__gte=today)
        
        for h in queryset:
            result.append({
                'Id': h.id,
                'Name': h.name,
                'StartDate': h.start_date,
                'EndDate': h.end_date,
                'CreatedBy': h.created_by,
                'CreatedOn': h.created_on,
                'CenterId': h.center_id,
                'CenterName': h.center.center_name if h.center else None
            })
        
        return result
            
    except Exception as e:
        logger.error(f"HolidaysHelper : GetAllHolidays : {str(e)}")
        raise e

def delete_holiday_by_id(holiday_id):
    """Soft delete holiday by ID - set status to False"""
    logger.info(f"HolidaysHelper : DeleteHolidayById : Started")
    
    try:
        holiday = Holidays.objects.filter(id=holiday_id).first()
        if not holiday:
            logger.error(f"Holiday not found with ID: {holiday_id}")
            return None
        
        # Soft delete - set status to False
        holiday.status = False
        holiday.updated_on = datetime.now()
        holiday.save()
        
        logger.info(f"HolidaysHelper : DeleteHolidayById : End")
        return {'id': holiday_id, 'deleted': True}
        
    except Exception as e:
        logger.error(f"HolidaysHelper : DeleteHolidayById : {str(e)}")
        raise e


#---------------------------------------------------------
# Panchayat APIs Helper Functions
#---------------------------------------------------------

def get_all_panchayats(offset, limit):
    """Get all panchayats with pagination"""
    logger.info(f"PanchayatHelper : GetAllPanchayat : Started")
    
    try:
        queryset = Panchayat.objects.filter(status=True).select_related('district', 'vidhan_sabha', 'vidhan_sabha__district').order_by('id')
        
        if offset > 0 or limit > 0:
            queryset = queryset[offset:offset + limit]
        
        result = []
        for p in queryset:
            result.append({
                'Id': p.id,
                'PanchayatGuidId': p.panchayat_guid_id,
                'Name': p.name,
                'DistrictId': p.district_id,
                'DistrictName': p.district.name if p.district else None,
                'VidhanSabhaId': p.vidhan_sabha_id,
                'VidhanSabhaName': p.vidhan_sabha.name if p.vidhan_sabha else None,
                'CreatedOn': p.created_on,
                'CreatedBy': p.created_by,
                'Status': p.status
            })
        return result
            
    except Exception as e:
        logger.error(f"PanchayatHelper : GetAllPanchayat : {str(e)}")
        raise e

def save_panchayat(panchayat_data):
    """Save or update panchayat"""
    logger.info(f"PanchayatHelper : SavePanchayat : Started")
    
    try:
        panchayat_id = int(panchayat_data.get('Id', 0))
        
        if panchayat_id > 0:
            # Update existing panchayat - NEVER update PanchayatGuidId
            try:
                panchayat = Panchayat.objects.get(id=panchayat_id)
                
                # Update fields
                if 'Name' in panchayat_data and panchayat_data['Name'] is not None:
                    panchayat.name = panchayat_data['Name']
                if 'Status' in panchayat_data and panchayat_data['Status'] is not None:
                    panchayat.status = panchayat_data['Status']
                if 'DistrictId' in panchayat_data and panchayat_data['DistrictId'] is not None:
                    panchayat.district_id = panchayat_data['DistrictId']
                if 'VidhanSabhaId' in panchayat_data and panchayat_data['VidhanSabhaId'] is not None:
                    panchayat.vidhan_sabha_id = panchayat_data['VidhanSabhaId']
                if 'CreatedBy' in panchayat_data and panchayat_data['CreatedBy'] is not None:
                    panchayat.created_by = panchayat_data['CreatedBy']
                
                # Always update timestamps
                panchayat.updated_on = datetime.now()
                updated_by = panchayat_data.get('UpdatedBy') or panchayat_data.get('CreatedBy')
                if updated_by:
                    panchayat.updated_by = updated_by
                
                panchayat.save()
                
            except Panchayat.DoesNotExist:
                logger.error(f"Panchayat not found with ID: {panchayat_id}")
                return None
        else:
            # Insert new panchayat
            panchayat_guid = str(uuid.uuid4())
            
            panchayat = Panchayat(
                panchayat_guid_id=panchayat_guid,
                name=panchayat_data.get('Name'),
                status=panchayat_data.get('Status'),
                district_id=panchayat_data.get('DistrictId'),
                vidhan_sabha_id=panchayat_data.get('VidhanSabhaId'),
                created_on=datetime.now(),
                created_by=panchayat_data.get('CreatedBy')
            )
            panchayat.save()
            panchayat_id = panchayat.id
        
        # Get the saved panchayat
        return get_panchayat_by_id(panchayat_id)
        
    except Exception as e:
        logger.error(f"PanchayatHelper : SavePanchayat : {str(e)}")
        raise e

def get_panchayat_by_id(panchayat_id):
    """Get panchayat by ID"""
    try:
        panchayat = Panchayat.objects.filter(id=panchayat_id, status=True).select_related('district', 'vidhan_sabha').first()
        if panchayat:
            return {
                'Id': panchayat.id,
                'PanchayatGuidId': panchayat.panchayat_guid_id,
                'Name': panchayat.name,
                'DistrictId': panchayat.district_id,
                'DistrictName': panchayat.district.name if panchayat.district else None,
                'VidhanSabhaId': panchayat.vidhan_sabha_id,
                'VidhanSabhaName': panchayat.vidhan_sabha.name if panchayat.vidhan_sabha else None,
                'CreatedOn': panchayat.created_on,
                'CreatedBy': panchayat.created_by,
                'Status': panchayat.status
            }
        return None
    except Exception as e:
        logger.error(f"PanchayatHelper : get_panchayat_by_id : {str(e)}")
        raise e

def get_panchayat_by_district_and_vidhan_sabha_id(district_id, vidhan_sabha_id):
    """Get panchayat by district and vidhan sabha ID"""
    logger.info(f"PanchayatHelper : GetPanchayatByDistrictAndVidhanSabhaId : Started")
    
    try:
        panchayat = Panchayat.objects.filter(district_id=district_id, vidhan_sabha_id=vidhan_sabha_id, status=True).first()
        if panchayat:
            return {
                'Id': panchayat.id,
                'PanchayatGuidId': panchayat.panchayat_guid_id,
                'Name': panchayat.name,
                'DistrictId': panchayat.district_id,
                'VidhanSabhaId': panchayat.vidhan_sabha_id,
                'CreatedOn': panchayat.created_on,
                'CreatedBy': panchayat.created_by,
                'Status': panchayat.status
            }
        return None
        
    except Exception as e:
        logger.error(f"PanchayatHelper : GetPanchayatByDistrictAndVidhanSabhaId : {str(e)}")
        raise e

def check_panchayat_name(name):
    """Check if panchayat name exists"""
    logger.info(f"PanchayatHelper : CheckPanchayatName : Started")
    
    try:
        return Panchayat.objects.filter(name=name).values_list('name', flat=True).first()
    except Exception as e:
        logger.error(f"PanchayatHelper : CheckPanchayatName : {str(e)}")
        raise e
    
    
#---------------------------------------------------------
# Student APIs Helper Functions
#---------------------------------------------------------

def save_student(student_data):
    """Save or update student"""
    logger.info(f"StudentHelper : SaveStudent : Started")
    
    try:
        student_id = student_data.get('Id', 0)
        
        if student_id > 0:
            # Update existing student
            try:
                student = Student.objects.get(id=student_id)
                
                # Preserve these fields from existing record
                status = student.status
                last_class = student.last_class
                active_class_status = student.active_class_status
                counter = student.counter
                
                # Update fields from request data
                if student_data.get('EnrollmentId') is not None:
                    student.enrollment_id = student_data['EnrollmentId']
                if student_data.get('FullName') is not None:
                    student.full_name = student_data['FullName']
                if student_data.get('MotherName') is not None:
                    student.mother_name = student_data['MotherName']
                if student_data.get('FatherName') is not None:
                    student.father_name = student_data['FatherName']
                if student_data.get('Age') is not None:
                    student.age = student_data['Age']
                if student_data.get('Gender') is not None:
                    student.gender = student_data['Gender']
                if student_data.get('Contact') is not None:
                    student.contact = student_data['Contact']
                if student_data.get('DateOfBirth') is not None:
                    student.date_of_birth = student_data['DateOfBirth']
                if student_data.get('Email') is not None:
                    student.email = student_data['Email']
                if student_data.get('Remarks') is not None:
                    student.remarks = student_data['Remarks']
                if student_data.get('Grade') is not None:
                    student.grade = student_data['Grade']
                if student_data.get('PhoneNumber') is not None:
                    student.phone_number = student_data['PhoneNumber']
                if student_data.get('ProfileImage') is not None:
                    student.profile_image = student_data['ProfileImage']
                if student_data.get('WhatsApp') is not None:
                    student.whats_app = student_data['WhatsApp']
                if student_data.get('FullAddress') is not None:
                    student.full_address = student_data['FullAddress']
                if student_data.get('JoiningDate') is not None:
                    student.joining_date = student_data['JoiningDate']
                if student_data.get('VidhanSabhaId') is not None:
                    student.vidhan_sabha_id = student_data['VidhanSabhaId']
                if student_data.get('DistrictId') is not None:
                    student.district_id = student_data['DistrictId']
                if student_data.get('PanchayatId') is not None:
                    student.panchayat_id = student_data['PanchayatId']
                if student_data.get('CenterId') is not None:
                    student.center_id = student_data['CenterId']
                # if student_data.get('CreatedBy') is not None:
                #     student.created_by = student_data['CreatedBy']
                if student_data.get('VillageId') is not None:
                    student.village_id = student_data['VillageId']
                if student_data.get('Education') is not None:
                    student.education = student_data['Education']
                if student_data.get('FatherMobileNumber') is not None:
                    student.father_mobile_number = student_data['FatherMobileNumber']
                if student_data.get('FatherOccupation') is not None:
                    student.father_occupation = student_data['FatherOccupation']
                if student_data.get('MotherMobileNumber') is not None:
                    student.mother_mobile_number = student_data['MotherMobileNumber']
                if student_data.get('MotherOccupation') is not None:
                    student.mother_occupation = student_data['MotherOccupation']
                if student_data.get('Category') is not None:
                    student.category = student_data['Category']
                if student_data.get('SchoolId') is not None:
                    student.school_id = student_data['SchoolId']
                
                # Preserve existing values (matches .NET logic)
                student.bpl = False
                student.status = status
                student.last_class = last_class
                student.active_class_status = active_class_status
                student.counter = counter
                student.updated_on = datetime.now()
                student.updated_by = student_data.get('CreatedBy')
                student.manual_attendance = 0
                
                student.save()
                
            except Student.DoesNotExist:
                logger.error(f"Student not found with ID: {student_id}")
                return None
        else:
            # Insert new student
            enrollment_id = student_data.get('EnrollmentId') or str(uuid.uuid4())
            
            student = Student(
                enrollment_id=enrollment_id,
                full_name=student_data.get('FullName'),
                mother_name=student_data.get('MotherName'),
                father_name=student_data.get('FatherName'),
                age=student_data.get('Age'),
                gender=student_data.get('Gender'),
                contact=student_data.get('Contact'),
                date_of_birth=student_data.get('DateOfBirth'),
                email=student_data.get('Email'),
                remarks=student_data.get('Remarks'),
                grade=student_data.get('Grade'),
                phone_number=student_data.get('PhoneNumber'),
                profile_image=student_data.get('ProfileImage'),
                whats_app=student_data.get('WhatsApp'),
                full_address=student_data.get('FullAddress'),
                joining_date=student_data.get('JoiningDate'),
                vidhan_sabha_id=student_data.get('VidhanSabhaId'),
                district_id=student_data.get('DistrictId'),
                panchayat_id=student_data.get('PanchayatId'),
                center_id=student_data.get('CenterId'),
                created_by=student_data.get('CreatedBy'),
                village_id=student_data.get('VillageId'),
                education=student_data.get('Education'),
                father_mobile_number=student_data.get('FatherMobileNumber'),
                father_occupation=student_data.get('FatherOccupation'),
                mother_mobile_number=student_data.get('MotherMobileNumber'),
                mother_occupation=student_data.get('MotherOccupation'),
                category=student_data.get('Category'),
                bpl=student_data.get('Bpl') or False,
                school_id=student_data.get('SchoolId'),
                status=True,
                created_on=datetime.now(),
                active_class_status=False,
                manual_attendance=0
            )
            student.save()
            student_id = student.id
        
        # Get the saved student
        return get_student_by_id(student_id)
        
    except Exception as e:
        logger.error(f"StudentHelper : SaveStudent : {str(e)}")
        raise e
    
def get_student_by_id(student_id):
    """Get student by ID"""
    logger.info(f"StudentHelper : GetStudentById : Started")
    
    try:
        sql = """
            SELECT 
                s.Id,
                s.EnrollmentId,
                s.FullName,
                s.MotherName,
                s.FatherName,
                s.Age,
                s.Gender,
                s.Contact,
                s.DateOfBirth,
                s.Email,
                s.Remarks,
                s.Grade,
                s.PhoneNumber,
                s.ProfileImage,
                s.WhatsApp,
                s.FullAddress,
                s.Status,
                s.JoiningDate,
                s.CenterId,
                s.DistrictId,
                s.VidhanSabhaId,
                s.VillageId,
                s.PanchayatId,
                s.FatherMobileNumber,
                s.FatherOccupation,
                s.MotherMobileNumber,
                s.MotherOccupation,
                s.Category,
                s.Bpl,
                s.SchoolId,
                sc.SchoolName,
                c.CenterName,
                u.Name as TeacherName
            FROM Student s
            LEFT JOIN School sc ON s.SchoolId = sc.Id
            LEFT JOIN Center c ON s.CenterId = c.Id
            LEFT JOIN Users u ON c.AssignedTeachers = u.Id
            WHERE s.Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [student_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
        
    except Exception as e:
        logger.error(f"StudentHelper : GetStudentById : {str(e)}")
        raise e

def update_student_active_or_inactive(student_id, status,request):
    """Update student active or inactive status"""
    logger.info(f"StudentHelper : UpdateStudentActiveOrInactive : Started")
    current_user_id = get_user_id_from_token(request)
    
    try:
        status_bool = True if status == 1 else False
        
        student = Student.objects.filter(id=student_id).first()
        if not student:
            logger.error(f"Student not found with ID: {student_id}")
            return None
        
        student.status = status_bool
        student.updated_on = datetime.now()
        student.save()
        
        return get_student_by_id(student_id)
        
    except Exception as e:
        logger.error(f"StudentHelper : UpdateStudentActiveOrInactive : {str(e)}")
        raise e

def get_total_student_present(scan_date, user_id):
    """Get total student present count - matches .NET response exactly"""
    logger.info(f"StudentHelper : GetTotalStudentPresent : Started")
    
    try:
        # Get user type
        try:
            user = User.objects.get(id=user_id)
            user_type = user.role_id
        except User.DoesNotExist:
            logger.error(f"User not found with ID: {user_id}")
            return {
                'totalStudents': 0,
                'presentStudents': 0,
                'totalClasses': 0,
                'totalActiveClasses': 0,
                'completedClassCount': 0,
                'upComingClassCount': 0,
                'cancelClassCount': 0,
                'time': None
            }
        
        # Get center IDs based on user type
        if user_type == 1:  # SuperAdmin
            center_ids = list(Center.objects.filter(status=True).values_list('id', flat=True))
        else:  # Regional Admin (Type 2)
            center_ids = list(Center.objects.filter(
                assigned_regional_admin=user_id, status=True
            ).values_list('id', flat=True))
        
        if not center_ids:
            return {
                'totalStudents': 0,
                'presentStudents': 0,
                'totalClasses': 0,
                'totalActiveClasses': 0,
                'completedClassCount': 0,
                'upComingClassCount': 0,
                'cancelClassCount': 0,
                'time': None
            }
        
        # 1. Get Total Students and Present Students
        # Total active students
        total_students = Student.objects.filter(
            center_id__in=center_ids,
            status=True
        ).count()
        
        # Present students (attendance on scan_date)
        scan_date_obj = scan_date.date() if hasattr(scan_date, 'date') else scan_date
        present_students = StudentAttendance.objects.filter(
            center_id__in=center_ids,
            scan_date__date=scan_date_obj
        ).values('student_id').distinct().count()
        
        # 2. Get Total Classes and Active Classes
        total_classes = Center.objects.filter(
            id__in=center_ids
        ).count()
        
        active_classes = ClassModel.objects.filter(
            center_id__in=center_ids,
            status=1,  # Active status
            started_date__date=scan_date_obj
        ).count()
        
        # 3. Get Completed and Upcoming Classes
        # Classes that started on scan_date
        classes_on_date = ClassModel.objects.filter(
            center_id__in=center_ids,
            started_date__date=scan_date_obj
        )
        
        completed_class_count = classes_on_date.filter(
            status=2  # Completed status
        ).count()
        
        # Centers that don't have a class on scan_date (upcoming)
        center_ids_with_class = classes_on_date.values_list('center_id', flat=True)
        upcoming_class_count = Center.objects.filter(
            id__in=center_ids
        ).exclude(
            id__in=center_ids_with_class
        ).count()
        
        # 4. Get Cancel Class Count
        today = datetime.now().date()
        cancel_class_count = ClassCancelByTeacher.objects.filter(
            center_id__in=center_ids,
            starting_date__date__lte=today,
            ending_date__date__gte=today
        ).count()
        
        return {
            'totalStudents': total_students,
            'presentStudents': present_students,
            'totalClasses': total_classes,
            'totalActiveClasses': active_classes,
            'completedClassCount': completed_class_count,
            'upComingClassCount': upcoming_class_count,
            'cancelClassCount': cancel_class_count,
            'time': None
        }
        
    except Exception as e:
        logger.error(f"StudentHelper : GetTotalStudentPresent : {str(e)}")
        raise e

def get_all_students(user_id, district_id=0, vidhan_sabha_id=0, panchayat_id=0, village_id=0):
    """Get all students with filters"""
    logger.info(f"StudentHelper : GetAllStudents : Started")
    
    try:
        # Get user type
        user_type_sql = "SELECT Type FROM Users WHERE Id = %s"
        with connection.cursor() as cursor:
            cursor.execute(user_type_sql, [user_id])
            user_row = cursor.fetchone()
            user_type = user_row[0] if user_row else None
        
        where_conditions = ["1=1"]
        params = []
        
        if user_type == 1:
            # SuperAdmin - can see all students
            if district_id:
                where_conditions.append("DistrictId = %s")
                params.append(district_id)
            if vidhan_sabha_id:
                where_conditions.append("VidhanSabhaId = %s")
                params.append(vidhan_sabha_id)
            if panchayat_id:
                where_conditions.append("PanchayatId = %s")
                params.append(panchayat_id)
            if village_id:
                where_conditions.append("VillageId = %s")
                params.append(village_id)
        else:
            # Regional Admin - only see students in their centers
            center_sql = "SELECT Id FROM Center WHERE AssignedRegionalAdmin = %s"
            cursor.execute(center_sql, [user_id])
            center_rows = cursor.fetchall()
            center_ids = [row[0] for row in center_rows]
            
            if center_ids:
                center_ids_str = ','.join(['%s'] * len(center_ids))
                where_conditions.append(f"CenterId IN ({center_ids_str})")
                params.extend(center_ids)
                
                if district_id:
                    where_conditions.append("DistrictId = %s")
                    params.append(district_id)
                if vidhan_sabha_id:
                    where_conditions.append("VidhanSabhaId = %s")
                    params.append(vidhan_sabha_id)
                if panchayat_id:
                    where_conditions.append("PanchayatId = %s")
                    params.append(panchayat_id)
                if village_id:
                    where_conditions.append("VillageId = %s")
                    params.append(village_id)
            else:
                return []
        
        where_clause = " AND ".join(where_conditions)
        sql = f"SELECT * FROM Student WHERE {where_clause}"
        
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
            return result
            
    except Exception as e:
        logger.error(f"StudentHelper : GetAllStudents : {str(e)}")
        raise e
    
    
#---------------------------------------------------------
# School APIs Helper Functions
#---------------------------------------------------------

def save_school(school_data):
    """Save or update school - Matches .NET School/SaveSchool logic"""
    logger.info(f"SchoolHelper : SaveSchool : Started")
    
    try:
        school_id = school_data.get('Id', 0)
        
        if school_id > 0:
            # Update existing school
            try:
                school = School.objects.get(id=school_id)
                
                # Update fields
                if 'SchoolName' in school_data and school_data['SchoolName'] is not None:
                    school.school_name = school_data['SchoolName']
                
                school.updated_on = datetime.now()
                school.updated_by = school_data.get('UpdatedBy') or school_data.get('CreatedBy')
                school.save()
                
                # Get updated school
                return get_school_by_id(school_id)
                
            except School.DoesNotExist:
                logger.error(f"School not found with ID: {school_id}")
                return None
        else:
            # Insert new school
            school = School(
                school_name=school_data.get('SchoolName'),
                created_on=datetime.now(),
                created_by=school_data.get('CreatedBy'),
                status=True
            )
            school.save()
            school_id = school.id
        
        # Get the saved school with serializer format
        return get_school_by_id(school_id)
        
    except IntegrityError as e:
        logger.error(f"SchoolHelper : SaveSchool : IntegrityError - {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"SchoolHelper : SaveSchool : {str(e)}")
        raise e

def get_school_by_id(school_id):
    """Get school by ID"""
    try:
        school = School.objects.filter(id=school_id).first()
        if school:
            return {
                'Id': school.id,
                'SchoolName': school.school_name,
                'CreatedOn': school.created_on,
                'CreatedBy': school.created_by
            }
        return None
    except Exception as e:
        logger.error(f"SchoolHelper : get_school_by_id : {str(e)}")
        raise e

def get_all_schools():
    """Get all schools"""
    logger.info(f"SchoolHelper : GetAllSchools : Started")
    
    try:
        schools = School.objects.all().order_by('id')
        result = []
        for s in schools:
            result.append({
                'Id': s.id,
                'SchoolName': s.school_name,
                'CreatedOn': s.created_on,
                'CreatedBy': s.created_by
            })
        return result
    except Exception as e:
        logger.error(f"SchoolHelper : GetAllSchools : {str(e)}")
        raise e
    
#---------------------------------------------------------
# StudentAttendance APIs Helper Functions
#---------------------------------------------------------

def save_student_attendance(attendance_data, is_automatic=False, is_manual=False):
    """Save student attendance"""
    logger.info(f"StudentAttendanceHelper : SaveStudentAttendance : Started")
    
    try:
        student_ids = attendance_data.get('StudentIds', [])
        class_id = attendance_data.get('ClassId')
        center_id = attendance_data.get('CenterId')
        user_id = attendance_data.get('UserId')
        scan_date = attendance_data.get('ScanDate')
        
        if not student_ids:
            return -1
        
        for student_id in student_ids:
            # Check if student is active
            check_sql = "SELECT Status, CenterId, ManualAttendance FROM Student WHERE Id = %s"
            with connection.cursor() as cursor:
                cursor.execute(check_sql, [student_id])
                student_row = cursor.fetchone()
                
                if not student_row:
                    continue
                
                if not is_automatic and not is_manual:
                    # SaveStudentAttendance
                    if not student_row[0]:  # Status is False
                        return 0
                    if student_row[1] != center_id:
                        return -2
                
                if is_automatic:
                    # SaveAutomaticStudentAttendance
                    if not student_row[0]:
                        return 0
                    if student_row[1] != center_id:
                        return -2
                
                if is_manual:
                    # SaveManualStudentAttendance
                    manual_attendance = student_row[2] or 0
                    if manual_attendance >= 360:
                        return 0
                
                # Check if attendance already exists for today
                today = datetime.now().date()
                if is_automatic or is_manual:
                    check_attendance_sql = """
                        SELECT Id FROM StudentAttendance 
                        WHERE StudentId = %s AND ClassId = %s AND DATE(ScanDate) = %s
                    """
                    cursor.execute(check_attendance_sql, [student_id, class_id, today])
                    if cursor.fetchone():
                        return -1
                else:
                    check_attendance_sql = """
                        SELECT Id FROM StudentAttendance 
                        WHERE StudentId = %s AND ClassId = %s AND DATE(ScanDate) = %s
                    """
                    cursor.execute(check_attendance_sql, [student_id, class_id, scan_date.date()])
                    if cursor.fetchone():
                        return -1
                
                # Insert attendance
                insert_sql = """
                    INSERT INTO StudentAttendance (ClassId, StudentId, CenterId, UserId, ScanDate, Type)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                attendance_type = True if is_manual else False
                scan_date_val = datetime.now() if (is_automatic or is_manual) else scan_date
                cursor.execute(insert_sql, [class_id, student_id, center_id, user_id, scan_date_val, attendance_type])
                
                # Update student ActiveClassStatus
                update_student_sql = "UPDATE Student SET ActiveClassStatus = 1 WHERE Id = %s"
                cursor.execute(update_student_sql, [student_id])
                
                # Update manual attendance count
                if is_manual:
                    update_manual_sql = "UPDATE Student SET ManualAttendance = ManualAttendance + 1 WHERE Id = %s"
                    cursor.execute(update_manual_sql, [student_id])
                
                # Update class avilable students
                update_class_sql = "UPDATE Class SET AvilableStudents = AvilableStudents + 1 WHERE Id = %s"
                cursor.execute(update_class_sql, [class_id])
        
        return 1
        
    except Exception as e:
        logger.error(f"StudentAttendanceHelper : SaveStudentAttendance : {str(e)}")
        raise e

def get_all_student_with_avg_attendance(center_id):
    """Get all students with average attendance """
    logger.info(f"StudentAttendanceHelper : GetAllStudentWihAvgAttendance : Started")
    
    try:
        # Get class count for this center (Active or Completed)
        class_count = ClassModel.objects.filter(
            center_id=center_id,
            status__in=[1, 2]  # Active (1) or Completed (2)
        ).count()
        
        students = []
        
        # Get all students in the center
        student_queryset = Student.objects.filter(
            center_id=center_id,
            status=True  # Only active students
        ).values(
            'id', 'enrollment_id', 'full_name', 'joining_date', 'status'
        )
        
        for student in student_queryset:
            student_id = student['id']
            
            # Count attendance for this student
            attendance_count = StudentAttendance.objects.filter(
                student_id=student_id
            ).count()
            
            # Calculate average attendance
            # avgAttendance = (attendance_count * 100) / class_count
            if class_count > 0:
                avg_attendance = (attendance_count * 100) / class_count
            else:
                avg_attendance = 0
            
            # Determine attendance status
            # This would be based on the student's attendance for a specific date
            # For now, we'll set it to None or you can calculate based on today's date
            attendance_status = None
            
            students.append({
                'id': student_id,
                'enrollmentId': student['enrollment_id'],
                'fullName': student['full_name'],
                'attendanceStatus': attendance_status,
                'averageAttendance': avg_attendance,
                'date': student['joining_date']  # Or you can use today's date
            })
        
        return students
        
    except Exception as e:
        logger.error(f"StudentAttendanceHelper : GetAllStudentWihAvgAttendance : {str(e)}")
        raise e

def get_all_absent_attendance(center_id):
    """Get all absent students"""
    logger.info(f"StudentAttendanceHelper : GetAllAbsentAttendance : Started")
    
    try:
        today = datetime.now().date()
        
        # Get all active students
        all_students_sql = "SELECT Id, FullName, EnrollmentId, ProfileImage, ManualAttendance FROM Student WHERE CenterId = %s AND Status = 1"
        with connection.cursor() as cursor:
            cursor.execute(all_students_sql, [center_id])
            all_students = cursor.fetchall()
            
            if not all_students:
                return []
            
            student_ids = [row[0] for row in all_students]
            student_ids_str = ','.join(['%s'] * len(student_ids))
            
            # Get students with attendance today
            present_sql = f"""
                SELECT DISTINCT StudentId 
                FROM StudentAttendance 
                WHERE CenterId = %s AND DATE(ScanDate) = %s
            """
            cursor.execute(present_sql, [center_id, today])
            present_rows = cursor.fetchall()
            present_ids = [row[0] for row in present_rows]
            
            result = []
            for student in all_students:
                if student[0] not in present_ids:
                    result.append({
                        'id': student[0],
                        'name': student[1],
                        'enrollmentId': student[2],
                        'profileImage': student[3],
                        'manualAttendance': student[4] or 0
                    })
            
            return result
            
    except Exception as e:
        logger.error(f"StudentAttendanceHelper : GetAllAbsentAttendance : {str(e)}")
        raise e

def get_all_student_attendance_status(center_id, scan_date):
    """Get all student attendance status for a specific date """
    logger.info(f"StudentAttendanceHelper : GetAllStudentAttendancStatus : Started")
    
    try:
        # Parse the scan date
        if isinstance(scan_date, str):
            scan_date = parse_any_datetime(scan_date)
            scan_date = scan_date.date() if scan_date else datetime.now().date()
        elif hasattr(scan_date, 'date'):
            scan_date = scan_date.date()
        
        students = []
        
        # Get all active students in the center
        student_queryset = Student.objects.filter(
            center_id=center_id,
            status=True  # Only active students
        ).values('id', 'enrollment_id', 'full_name')
        
        for student in student_queryset:
            student_id = student['id']
            
            # Check if student has attendance on the given date
            has_attendance = StudentAttendance.objects.filter(
                student_id=student_id,
                scan_date__date=scan_date
            ).exists()
            
            attendance_status = 'Present' if has_attendance else 'Absent'
            
            students.append({
                'id': student_id,
                'enrollmentId': student['enrollment_id'],
                'fullName': student['full_name'],
                'attendanceStatus': attendance_status,
                'averageAttendance': 0,  # Not calculated in this endpoint
                'date': scan_date
            })
        
        return students
        
    except Exception as e:
        logger.error(f"StudentAttendanceHelper : GetAllStudentAttendancStatus : {str(e)}")
        raise e

def get_all_student_attendance_by_month(center_id, student_id, month, year):
    """Get student attendance by month"""
    logger.info(f"StudentAttendanceHelper : GetAllStudentAttendancByMonth : Started")
    
    try:
        import calendar
        start_date = datetime(year, month, 1)
        end_date = start_date.replace(day=1, month=start_date.month + 1) - timedelta(days=1)
        
        # Get student details
        student_sql = "SELECT Id, FullName FROM Student WHERE Id = %s AND Status = 1 AND CenterId = %s"
        with connection.cursor() as cursor:
            cursor.execute(student_sql, [student_id, center_id])
            student_row = cursor.fetchone()
            
            if not student_row:
                return []
            
            student_name = student_row[1]
            
            # Get attendance records
            attendance_sql = """
                SELECT DISTINCT DATE(ScanDate) as Date
                FROM StudentAttendance
                WHERE StudentId = %s AND DATE(ScanDate) BETWEEN %s AND %s
            """
            cursor.execute(attendance_sql, [student_id, start_date.date(), end_date.date()])
            attendance_dates = [row[0] for row in cursor.fetchall()]
            
            result = []
            current_date = start_date
            while current_date <= end_date:
                status = 'Present' if current_date.date() in attendance_dates else 'Absent'
                result.append({
                    'id': student_id,
                    'fullName': student_name,
                    'date': current_date,
                    'attendanceStatus': status
                })
                current_date += timedelta(days=1)
            
            return result
            
    except Exception as e:
        logger.error(f"StudentAttendanceHelper : GetAllStudentAttendancByMonth : {str(e)}")
        raise e
    
    
#---------------------------------------------------------
# Teacher APIs Helper Functions
#---------------------------------------------------------

def login_teacher(name, password):
    """Login teacher by name and password"""
    logger.info(f"TeacherHelper : LoginTeacher : Started")
    
    try:
        hashed_password = hash_password(password)
        
        user = User.objects.filter(name=name, password=hashed_password, type=3, status=True).select_related('teacher').first()
        
        if user and hasattr(user, 'teacher') and user.teacher:
            teacher = user.teacher
            
            # Generate token
            token = AccessToken()
            token['teacher_id'] = teacher.id
            token['teacher_name'] = user.name
            token.set_exp(lifetime=timedelta(days=30))
            
            return {
                'Id': teacher.id,
                'TeacherGuidId': teacher.teacher_guid_id,
                'FullName': user.name,
                'Age': teacher.age,
                'Gender': teacher.gender,
                'DateOfBirth': teacher.date_of_birth,
                'PhoneNumber': user.phone_number,
                'WhatsApp': user.whats_app,
                'Email': user.email,
                'Status': user.status,
                'Count': teacher.count,
                'Picture': user.picture.url if user.picture else None,
                'Password': user.password,
                'FullAddress': teacher.full_address,
                'Education': teacher.education,
                'Token': str(token),
                'VidhanSabhaId': teacher.vidhan_sabha_id,
                'DistrictId': teacher.district_id,
                'PanchayatId': teacher.panchayat_id,
                'CenterId': teacher.center_id,
                'VillageId': teacher.village_id,
                'CreatedOn': teacher.created_on,
                'CreatedBy': teacher.created_by,
                'UserId': user.id,
                'UserName': user.name,
                'UserPhoneNumber': user.phone_number,
                'UserEmail': user.email,
                'UserPicture': user.picture.url if user.picture else None,
                'DistrictName': teacher.district.name if teacher.district else None,
                'VidhanSabhaName': teacher.vidhan_sabha.name if teacher.vidhan_sabha else None,
                'PanchayatName': teacher.panchayat.name if teacher.panchayat else None,
                'CenterName': teacher.center.center_name if teacher.center else None,
                'VillageName': teacher.village.name if teacher.village else None,
            }
        
        return None
        
    except Exception as e:
        logger.error(f"TeacherHelper : LoginTeacher : {str(e)}")
        raise e

def save_teacher(teacher_data):
    """Save or update teacher"""
    logger.info(f"TeacherHelper : SaveTeacher : Started")
    
    try:
        teacher_id = teacher_data.get('Id', 0)
        
        if teacher_id > 0:
            update_fields = []
            update_values = []
            
            for key, value in teacher_data.items():
                if key != 'Id' and value is not None:
                    column_name = {
                        'FullName': 'FullName',
                        'Age': 'Age',
                        'Gender': 'Gender',
                        'DateOfBirth': 'DateOfBirth',
                        'PhoneNumber': 'PhoneNumber',
                        'WhatsApp': 'WhatsApp',
                        'Email': 'Email',
                        'Status': 'Status',
                        'Count': 'Count',
                        'Picture': 'Picture',
                        'Password': 'Password',
                        'FullAddress': 'FullAddress',
                        'Education': 'Education',
                        'VidhanSabhaId': 'VidhanSabhaId',
                        'DistrictId': 'DistrictId',
                        'PanchayatId': 'PanchayatId',
                        'CenterId': 'CenterId',
                        'VillageId': 'VillageId'
                    }.get(key, key)
                    
                    update_fields.append(f"{column_name} = %s")
                    update_values.append(value)
            
            if update_fields:
                update_values.append(teacher_id)
                sql = f"UPDATE Teacher SET {', '.join(update_fields)} WHERE Id = %s"
                with connection.cursor() as cursor:
                    cursor.execute(sql, update_values)
        else:
            teacher_guid = str(uuid.uuid4())
            created_on = datetime.now()
            
            columns = ['TeacherGuidId', 'CreatedOn']
            values = [teacher_guid, created_on]
            
            field_mapping = {
                'FullName': 'FullName',
                'Age': 'Age',
                'Gender': 'Gender',
                'DateOfBirth': 'DateOfBirth',
                'PhoneNumber': 'PhoneNumber',
                'WhatsApp': 'WhatsApp',
                'Email': 'Email',
                'Status': 'Status',
                'Count': 'Count',
                'Picture': 'Picture',
                'Password': 'Password',
                'FullAddress': 'FullAddress',
                'Education': 'Education',
                'VidhanSabhaId': 'VidhanSabhaId',
                'DistrictId': 'DistrictId',
                'PanchayatId': 'PanchayatId',
                'CenterId': 'CenterId',
                'VillageId': 'VillageId'
            }
            
            for key, column in field_mapping.items():
                if key in teacher_data and teacher_data[key] is not None:
                    columns.append(column)
                    values.append(teacher_data[key])
            
            placeholders = ', '.join(['%s'] * len(columns))
            sql = f"INSERT INTO Teacher ({', '.join(columns)}) VALUES ({placeholders})"
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                cursor.execute("SELECT LAST_INSERT_ID()")
                teacher_id = cursor.fetchone()[0]
        
        return get_teacher_by_id(teacher_id)
        
    except Exception as e:
        logger.error(f"TeacherHelper : SaveTeacher : {str(e)}")
        raise e

def get_teacher_by_id(teacher_id):
    """Get teacher by User ID with User data joined"""
    try:
        teacher = Teacher.objects.filter(user__id=teacher_id).select_related(
            'user', 'district', 'vidhan_sabha', 'panchayat', 'center', 'village'
        ).first()
        
        if teacher and teacher.user and teacher.user.type == 3:
            user = teacher.user
            return {
                'Id': user.id,
                'TeacherGuidId': teacher.teacher_guid_id,
                'FullName': user.name,
                'Age': teacher.age,
                'Gender': teacher.gender,
                'DateOfBirth': teacher.date_of_birth,
                'PhoneNumber': user.phone_number,
                'WhatsApp': user.whats_app,
                'Email': user.email,
                'Status': user.status,
                'Count': teacher.count,
                'Picture': user.picture.url if user.picture else None,
                'Password': user.password,
                'FullAddress': teacher.full_address,
                'Education': teacher.education,
                'Token': user.token,
                'VidhanSabhaId': teacher.vidhan_sabha_id,
                'DistrictId': teacher.district_id,
                'PanchayatId': teacher.panchayat_id,
                'CenterId': teacher.center_id,
                'VillageId': teacher.village_id,
                'CreatedOn': teacher.created_on,
                'CreatedBy': teacher.created_by,
                'UserId': user.id,
                'UserName': user.name,
                'UserPhoneNumber': user.phone_number,
                'UserEmail': user.email,
                'UserPicture': user.picture.url if user.picture else None,
                'DistrictName': teacher.district.name if teacher.district else None,
                'VidhanSabhaName': teacher.vidhan_sabha.name if teacher.vidhan_sabha else None,
                'PanchayatName': teacher.panchayat.name if teacher.panchayat else None,
                'CenterName': teacher.center.center_name if teacher.center else None,
                'VillageName': teacher.village.name if teacher.village else None,
            }
        return None
    except Exception as e:
        logger.error(f"TeacherHelper : get_teacher_by_id : {str(e)}")
        raise e
    
    
#---------------------------------------------------------
# VidhanSabha APIs Helper Functions
#---------------------------------------------------------

def get_all_vidhan_sabhas(offset, limit):
    """Get all VidhanSabhas with pagination"""
    logger.info(f"VidhanSabhaHelper : GetAllVidhanSabha : Started")
    
    try:
        queryset = VidhanSabha.objects.filter(status=True).select_related('district').order_by('id')
        
        if offset > 0 or limit > 0:
            queryset = queryset[offset:offset + limit]
        
        result = []
        for v in queryset:
            result.append({
                'Id': v.id,
                'VidhanSabhaGuidId': v.vidhan_sabha_guid_id,
                'Name': v.name,
                'DistrictId': v.district_id,
                'DistrictName': v.district.name if v.district else None,
                'CreatedOn': v.created_on,
                'CreatedBy': v.created_by,
                'Status': v.status
            })
        return result
            
    except Exception as e:
        logger.error(f"VidhanSabhaHelper : GetAllVidhanSabha : {str(e)}")
        raise e

def save_vidhan_sabha(vidhan_sabha_data):
    """Save or update VidhanSabha"""
    logger.info(f"VidhanSabhaHelper : SaveVidhanSabha : Started")
    
    try:
        vidhan_sabha_id = vidhan_sabha_data.get('Id', 0)
        
        if vidhan_sabha_id > 0:
            # Update existing VidhanSabha
            try:
                vidhan_sabha = VidhanSabha.objects.get(id=vidhan_sabha_id)
                
                # Update fields (never update VidhanSabhaGuidId)
                if 'Name' in vidhan_sabha_data and vidhan_sabha_data['Name'] is not None:
                    vidhan_sabha.name = vidhan_sabha_data['Name']
                if 'Status' in vidhan_sabha_data and vidhan_sabha_data['Status'] is not None:
                    vidhan_sabha.status = vidhan_sabha_data['Status']
                if 'DistrictId' in vidhan_sabha_data and vidhan_sabha_data['DistrictId'] is not None:
                    vidhan_sabha.district_id = vidhan_sabha_data['DistrictId']
                
                # Always update timestamps
                vidhan_sabha.updated_on = datetime.now()
                updated_by = vidhan_sabha_data.get('UpdatedBy') or vidhan_sabha_data.get('CreatedBy')
                if updated_by:
                    vidhan_sabha.updated_by = updated_by
                
                vidhan_sabha.save()
                
            except VidhanSabha.DoesNotExist:
                logger.error(f"VidhanSabha not found with ID: {vidhan_sabha_id}")
                return None
        else:
            # Insert new VidhanSabha
            vidhan_sabha_guid = vidhan_sabha_data.get('VidhanSabhaGuidId')
            if not vidhan_sabha_guid or vidhan_sabha_guid == '00000000-0000-0000-0000-000000000000':
                vidhan_sabha_guid = str(uuid.uuid4())
            
            vidhan_sabha = VidhanSabha(
                vidhan_sabha_guid_id=vidhan_sabha_guid,
                name=vidhan_sabha_data.get('Name'),
                status=vidhan_sabha_data.get('Status'),
                district_id=vidhan_sabha_data.get('DistrictId'),
                created_on=datetime.now(),
                created_by=vidhan_sabha_data.get('CreatedBy')
            )
            vidhan_sabha.save()
            vidhan_sabha_id = vidhan_sabha.id
        
        # Get the saved VidhanSabha with related data
        return get_vidhan_sabha_by_id(vidhan_sabha_id)
        
    except Exception as e:
        logger.error(f"VidhanSabhaHelper : SaveVidhanSabha : {str(e)}")
        raise e

def get_vidhan_sabha_by_id(vidhan_sabha_id):
    """Get VidhanSabha by ID"""
    try:
        v = VidhanSabha.objects.filter(id=vidhan_sabha_id, status=True).select_related('district').first()
        if v:
            return {
                'Id': v.id,
                'VidhanSabhaGuidId': v.vidhan_sabha_guid_id,
                'Name': v.name,
                'DistrictId': v.district_id,
                'DistrictName': v.district.name if v.district else None,
                'CreatedOn': v.created_on,
                'CreatedBy': v.created_by,
                'Status': v.status
            }
        return None
    except Exception as e:
        logger.error(f"VidhanSabhaHelper : get_vidhan_sabha_by_id : {str(e)}")
        raise e

def get_vidhan_sabha_by_district_id(district_id):
    """Get VidhanSabha by district ID"""
    logger.info(f"VidhanSabhaHelper : GetVidhanSabhaByDistrictId : Started")
    
    try:
        v = VidhanSabha.objects.filter(district_id=district_id, status=True).first()
        if v:
            return {
                'Id': v.id,
                'VidhanSabhaGuidId': v.vidhan_sabha_guid_id,
                'Name': v.name,
                'DistrictId': v.district_id,
                'CreatedOn': v.created_on,
                'CreatedBy': v.created_by,
                'Status': v.status
            }
        return None
        
    except Exception as e:
        logger.error(f"VidhanSabhaHelper : GetVidhanSabhaByDistrictId : {str(e)}")
        raise e

def check_vidhan_sabha_name(name):
    """Check if VidhanSabha name exists"""
    logger.info(f"VidhanSabhaHelper : CheckVidhanSabhaName : Started")
    
    try:
        return VidhanSabha.objects.filter(name=name).values_list('name', flat=True).first()
    except Exception as e:
        logger.error(f"VidhanSabhaHelper : CheckVidhanSabhaName : {str(e)}")
        raise e
    
    
#---------------------------------------------------------
# Village APIs Helper Functions
#---------------------------------------------------------

def get_all_villages(offset, limit):
    """Get all villages with pagination"""
    logger.info(f"VillageHelper : GetAllVillage : Started")
    
    try:
        queryset = Village.objects.filter(status=True).select_related('district', 'vidhan_sabha', 'panchayat').order_by('id')
        
        if offset > 0 or limit > 0:
            queryset = queryset[offset:offset + limit]
        
        result = []
        for v in queryset:
            result.append({
                'Id': v.id,
                'VillageGuidId': v.village_guid_id,
                'Name': v.name,
                'DistrictId': v.district_id,
                'DistrictName': v.district.name if v.district else None,
                'VidhanSabhaId': v.vidhan_sabha_id,
                'VidhanSabhaName': v.vidhan_sabha.name if v.vidhan_sabha else None,
                'PanchayatId': v.panchayat_id,
                'PanchayatName': v.panchayat.name if v.panchayat else None,
                'CreatedOn': v.created_on,
                'CreatedBy': v.created_by,
                'Status': v.status
            })
        return result
            
    except Exception as e:
        logger.error(f"VillageHelper : GetAllVillage : {str(e)}")
        raise e

def save_village(village_data):
    """Save or update village"""
    logger.info(f"VillageHelper : SaveVillage : Started")
    
    try:
        village_id = village_data.get('Id', 0)
        
        if village_id > 0:
            # Update existing village - NEVER update VillageGuidId
            try:
                village = Village.objects.get(id=village_id)
                
                # Update fields
                if 'Name' in village_data and village_data['Name'] is not None:
                    village.name = village_data['Name']
                if 'Status' in village_data and village_data['Status'] is not None:
                    village.status = village_data['Status']
                if 'DistrictId' in village_data and village_data['DistrictId'] is not None:
                    village.district_id = village_data['DistrictId']
                if 'VidhanSabhaId' in village_data and village_data['VidhanSabhaId'] is not None:
                    village.vidhan_sabha_id = village_data['VidhanSabhaId']
                if 'PanchayatId' in village_data and village_data['PanchayatId'] is not None:
                    village.panchayat_id = village_data['PanchayatId']
                if 'CreatedBy' in village_data and village_data['CreatedBy'] is not None:
                    village.created_by = village_data['CreatedBy']
                
                # Always update timestamps
                village.updated_on = datetime.now()
                updated_by = village_data.get('UpdatedBy') or village_data.get('CreatedBy')
                if updated_by:
                    village.updated_by = updated_by
                
                village.save()
                
            except Village.DoesNotExist:
                logger.error(f"Village not found with ID: {village_id}")
                return None
        else:
            # Insert new village
            village_guid = str(uuid.uuid4())
            
            village = Village(
                village_guid_id=village_guid,
                name=village_data.get('Name'),
                status=village_data.get('Status'),
                district_id=village_data.get('DistrictId'),
                vidhan_sabha_id=village_data.get('VidhanSabhaId'),
                panchayat_id=village_data.get('PanchayatId'),
                created_on=datetime.now(),
                created_by=village_data.get('CreatedBy')
            )
            village.save()
            village_id = village.id
        
        # Get the saved village
        return get_village_by_id(village_id)
        
    except Exception as e:
        logger.error(f"VillageHelper : SaveVillage : {str(e)}")
        raise e

def get_village_by_id(village_id):
    """Get village by ID"""
    try:
        village = Village.objects.filter(id=village_id, status=True).select_related('district', 'vidhan_sabha', 'panchayat').first()
        if village:
            return {
                'Id': village.id,
                'VillageGuidId': village.village_guid_id,
                'Name': village.name,
                'DistrictId': village.district_id,
                'DistrictName': village.district.name if village.district else None,
                'VidhanSabhaId': village.vidhan_sabha_id,
                'VidhanSabhaName': village.vidhan_sabha.name if village.vidhan_sabha else None,
                'PanchayatId': village.panchayat_id,
                'PanchayatName': village.panchayat.name if village.panchayat else None,
                'CreatedOn': village.created_on,
                'CreatedBy': village.created_by,
                'Status': village.status
            }
        return None
    except Exception as e:
        logger.error(f"VillageHelper : get_village_by_id : {str(e)}")
        raise e

def get_village_by_district_vidhan_sabha_and_panchayat(district_id, vidhan_sabha_id, panchayat_id):
    """Get village by district, vidhan sabha and panchayat IDs"""
    logger.info(f"VillageHelper : GetVillageByDistrictVidhanSabhaAndPanchId : Started")
    
    try:
        village = Village.objects.filter(district_id=district_id, vidhan_sabha_id=vidhan_sabha_id, panchayat_id=panchayat_id, status=True).first()
        if village:
            return {
                'Id': village.id,
                'VillageGuidId': village.village_guid_id,
                'Name': village.name,
                'DistrictId': village.district_id,
                'VidhanSabhaId': village.vidhan_sabha_id,
                'PanchayatId': village.panchayat_id,
                'CreatedOn': village.created_on,
                'CreatedBy': village.created_by,
                'Status': village.status
            }
        return None
        
    except Exception as e:
        logger.error(f"VillageHelper : GetVillageByDistrictVidhanSabhaAndPanchId : {str(e)}")
        raise e
        return None
        
    except Exception as e:
        logger.error(f"VillageHelper : GetVillageByDistrictVidhanSabhaAndPanchId : {str(e)}")
        raise e

def check_village_name(name):
    """Check if village name exists"""
    logger.info(f"VillageHelper : CheckVillageName : Started")
    
    try:
        return Village.objects.filter(name=name).values_list('name', flat=True).first()
    except Exception as e:
        logger.error(f"VillageHelper : CheckVillageName : {str(e)}")
        raise e
    
#---------------------------------------------------------
# RegionalAdmin APIs Helper Functions
#---------------------------------------------------------

def get_all_regional_admins():
    """Get all regional admins (Type == RegionalAdmin)"""
    logger.info(f"UserHelper : GetAllRegionalAdmins : Started")
    
    try:
        sql = """
            SELECT 
                u.Id,
                u.Name,
                u.Picture
            FROM Users u
            WHERE u.roleId = 2
            ORDER BY u.Id DESC
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            
            result = []
            for row in rows:
                user_dict = dict(zip(columns, row))
                regional_admin_dto = {
                    'id': user_dict.get('Id'),
                    'name': user_dict.get('Name'),
                    'profile': user_dict.get('Picture')
                }
                result.append(regional_admin_dto)
        
        logger.info(f"UserHelper : GetAllRegionalAdmins : End")
        return result
        
    except Exception as e:
        logger.error(f"UserHelper : GetAllRegionalAdmins : {str(e)}")
        raise e

def login_regional_admin(name, password):
    """Login regional admin by name and password with User join"""
    logger.info(f"RegionalAdminHelper : LoginRegionalAdmin : Started")
    
    try:
        hashed_password = hash_password(password)
        
        # Find user = User.objects.filter(name=name, password=hashed_password, role_id=2, status=True).select_related('regional_admin').first()
        
        if user and hasattr(user, 'regional_admin') and user.regional_admin:
            regional_admin = user.regional_admin
            
            # Generate token
            token = AccessToken()
            token['regional_admin_id'] = regional_admin.id
            token['regional_admin_name'] = user.name
            token.set_exp(lifetime=timedelta(days=30))
            
            return {
                'Id': regional_admin.id,
                'RegionalAdminGuidId': regional_admin.regional_admin_guid_id,
                'FullName': user.name,
                'Age': regional_admin.age,
                'Gender': regional_admin.gender,
                'DateOfBirth': regional_admin.date_of_birth,
                'PhoneNumber': user.phone_number,
                'WhatsApp': regional_admin.whats_app if hasattr(regional_admin, 'whats_app') else None,
                'Email': user.email,
                'Contact': regional_admin.contact,
                'Status': user.status,
                'RoleId': user.role_id,
                'Picture': user.picture.url if user.picture else None,
                'LastLoginTime': regional_admin.last_login_time if hasattr(regional_admin, 'last_login_time') else None,
                'Password': user.password,
                'FullAddress': regional_admin.full_address,
                'Type': user.type,
                'Token': str(token),
                'VidhanSabhaId': regional_admin.vidhan_sabha_id,
                'DistrictId': regional_admin.district_id,
                'PanchayatId': regional_admin.panchayat_id,
                'CenterId': regional_admin.center_id,
                'VillageId': regional_admin.village_id,
                'CreatedOn': regional_admin.created_on,
                'CreatedBy': regional_admin.created_by,
                'UserId': user.id,
                'UserName': user.name,
                'UserPhoneNumber': user.phone_number,
                'UserEmail': user.email,
                'UserPicture': user.picture.url if user.picture else None,
                'DistrictName': regional_admin.district.name if regional_admin.district else None,
                'VidhanSabhaName': regional_admin.vidhan_sabha.name if regional_admin.vidhan_sabha else None,
                'PanchayatName': regional_admin.panchayat.name if regional_admin.panchayat else None,
                'CenterName': regional_admin.center.center_name if regional_admin.center else None,
                'VillageName': regional_admin.village.name if regional_admin.village else None,
            }
        
        return None
        
    except Exception as e:
        logger.error(f"RegionalAdminHelper : LoginRegionalAdmin : {str(e)}")
        raise e

def save_regional_admin(regional_admin_data):
    """Save or update regional admin"""
    logger.info(f"RegionalAdminHelper : SaveRegionalAdmin : Started")
    
    try:
        regional_admin_id = regional_admin_data.get('Id', 0)
        
        if regional_admin_id > 0:
            update_fields = []
            update_values = []
            
            for key, value in regional_admin_data.items():
                if key != 'Id' and value is not None:
                    column_name = {
                        'FullName': 'FullName',
                        'Age': 'Age',
                        'Gender': 'Gender',
                        'DateOfBirth': 'DateOfBirth',
                        'PhoneNumber': 'PhoneNumber',
                        'WhatsApp': 'WhatsApp',
                        'Email': 'Email',
                        'Contact': 'Contact',
                        'Status': 'Status',
                        'RoleId': 'RoleId',
                        'Picture': 'Picture',
                        'Password': 'Password',
                        'FullAddress': 'FullAddress',
                        'Type': 'Type',
                        'VidhanSabhaId': 'VidhanSabhaId',
                        'DistrictId': 'DistrictId',
                        'PanchayatId': 'PanchayatId',
                        'CenterId': 'CenterId',
                        'VillageId': 'VillageId'
                    }.get(key, key)
                    
                    update_fields.append(f"{column_name} = %s")
                    update_values.append(value)
            
            if update_fields:
                update_values.append(regional_admin_id)
                sql = f"UPDATE RegionalAdmin SET {', '.join(update_fields)} WHERE Id = %s"
                with connection.cursor() as cursor:
                    cursor.execute(sql, update_values)
        else:
            regional_admin_guid = str(uuid.uuid4())
            created_on = datetime.now()
            
            columns = ['RegionalAdminGuidId', 'Type', 'CreatedOn']
            values = [regional_admin_guid, 2, created_on]
            
            field_mapping = {
                'FullName': 'FullName',
                'Age': 'Age',
                'Gender': 'Gender',
                'DateOfBirth': 'DateOfBirth',
                'PhoneNumber': 'PhoneNumber',
                'WhatsApp': 'WhatsApp',
                'Email': 'Email',
                'Contact': 'Contact',
                'Status': 'Status',
                'RoleId': 'RoleId',
                'Picture': 'Picture',
                'Password': 'Password',
                'FullAddress': 'FullAddress',
                'VidhanSabhaId': 'VidhanSabhaId',
                'DistrictId': 'DistrictId',
                'PanchayatId': 'PanchayatId',
                'CenterId': 'CenterId',
                'VillageId': 'VillageId'
            }
            
            for key, column in field_mapping.items():
                if key in regional_admin_data and regional_admin_data[key] is not None:
                    columns.append(column)
                    values.append(regional_admin_data[key])
            
            placeholders = ', '.join(['%s'] * len(columns))
            sql = f"INSERT INTO RegionalAdmin ({', '.join(columns)}) VALUES ({placeholders})"
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                cursor.execute("SELECT LAST_INSERT_ID()")
                regional_admin_id = cursor.fetchone()[0]
        
        return get_regional_admin_by_id(regional_admin_id)
        
    except Exception as e:
        logger.error(f"RegionalAdminHelper : SaveRegionalAdmin : {str(e)}")
        raise e

def get_regional_admin_by_id(regional_admin_id):
    """Get regional admin by User ID with User data joined"""
    try:
        regional_admin = RegionalAdmin.objects.filter(user__id=regional_admin_id).select_related(
            'user', 'district', 'vidhan_sabha', 'panchayat', 'center', 'village'
        ).first()
        if regional_admin and regional_admin.user and regional_admin.user.role_id == 2:
            user = regional_admin.user
            return {
                'Id': user.id,
                'RegionalAdminGuidId': regional_admin.regional_admin_guid_id,
                'FullName': user.name,
                'Age': regional_admin.age,
                'Gender': regional_admin.gender,
                'DateOfBirth': regional_admin.date_of_birth,
                'PhoneNumber': user.phone_number,
                'WhatsApp': user.whats_app,
                'Email': user.email,
                'Contact': regional_admin.contact,
                'Status': user.status,
                'RoleId': user.role_id,
                'Picture': user.picture.url if user.picture else None,
                'LastLoginTime': user.last_login_time,
                'Password': user.password,
                'FullAddress': regional_admin.full_address,
                'Type': user.type,
                'Token': user.token,
                'VidhanSabhaId': regional_admin.vidhan_sabha_id,
                'DistrictId': regional_admin.district_id,
                'PanchayatId': regional_admin.panchayat_id,
                'CenterId': regional_admin.center_id,
                'VillageId': regional_admin.village_id,
                'CreatedOn': regional_admin.created_on,
                'CreatedBy': regional_admin.created_by,
                'UserId': user.id,
                'UserName': user.name,
                'UserPhoneNumber': user.phone_number,
                'UserEmail': user.email,
                'UserPicture': user.picture.url if user.picture else None,
                'DistrictName': regional_admin.district.name if regional_admin.district else None,
                'VidhanSabhaName': regional_admin.vidhan_sabha.name if regional_admin.vidhan_sabha else None,
                'PanchayatName': regional_admin.panchayat.name if regional_admin.panchayat else None,
                'CenterName': regional_admin.center.center_name if regional_admin.center else None,
                'VillageName': regional_admin.village.name if regional_admin.village else None,
            }
        return None
    except Exception as e:
        logger.error(f"RegionalAdminHelper : get_regional_admin_by_id : {str(e)}")
        raise e
    
#---------------------------------------------------------
# Announcement APIs Helper Functions
#---------------------------------------------------------

def save_announcement(announcement_data):
    """Save or update announcement"""
    logger.info(f"AnnouncementHelper : SaveAnnouncement : Started")
    
    try:
        announcement_id = announcement_data.get('Id', 0)
        
        if announcement_id > 0:
            # Update existing announcement
            update_fields = []
            update_values = []
            
            for key, value in announcement_data.items():
                if key != 'Id' and value is not None:
                    column_name = {
                        'Title': 'Title',
                        'Description': 'Description',
                        'Image': 'Image',
                        'CreatedOn': 'CreatedOn',
                        'CreatedBy': 'CreatedBy'
                    }.get(key, key)
                    
                    update_fields.append(f"{column_name} = %s")
                    update_values.append(value)
            
            if update_fields:
                update_values.append(announcement_id)
                sql = f"UPDATE Announcement SET {', '.join(update_fields)} WHERE Id = %s"
                with connection.cursor() as cursor:
                    cursor.execute(sql, update_values)
        else:
            # Insert new announcement
            sql = """
                INSERT INTO Announcement (Title, Description, Image, CreatedOn, CreatedBy)
                VALUES (%s, %s, %s, %s, %s)
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [
                    announcement_data.get('Title'),
                    announcement_data.get('Description'),
                    announcement_data.get('Image'),
                    announcement_data.get('CreatedOn') or datetime.now(),
                    announcement_data.get('CreatedBy')
                ])
                cursor.execute("SELECT LAST_INSERT_ID()")
                announcement_id = cursor.fetchone()[0]
        
        return get_announcement_by_id(announcement_id)
        
    except Exception as e:
        logger.error(f"AnnouncementHelper : SaveAnnouncement : {str(e)}")
        raise e

def get_announcement_by_id(announcement_id):
    """Get announcement by ID"""
    try:
        announcement = Announcement.objects.filter(id=announcement_id, status=True).first()
        if announcement:
            return {
                'Id': announcement.id,
                'Title': announcement.title,
                'Description': announcement.description,
                'Image': announcement.image,
                'CreatedOn': announcement.created_on,
                'CreatedBy': announcement.created_by
            }
        return None
    except Exception as e:
        logger.error(f"AnnouncementHelper : get_announcement_by_id : {str(e)}")
        raise e

def get_all_announcements():
    """Get all announcements"""
    logger.info(f"AnnouncementHelper : GetAnnouncement : Started")
    
    try:
        announcements = Announcement.objects.filter(status=True).order_by('id')
        result = []
        for a in announcements:
            result.append({
                'Id': a.id,
                'Title': a.title,
                'Description': a.description,
                'Image': a.image,
                'CreatedOn': a.created_on,
                'CreatedBy': a.created_by
            })
        return result
    except Exception as e:
        logger.error(f"AnnouncementHelper : GetAnnouncement : {str(e)}")
        raise e

def upload_announcement_images(image_files):
    """Upload announcement images"""
    try:
        file_paths = []
        for image_file in image_files:
            if image_file:
                # Create unique filename
                file_extension = os.path.splitext(image_file.name)[1]
                file_name = f"announcement_{uuid.uuid4()}{file_extension}"
                file_path = f"AnnouncementImages/{file_name}"
                
                # Save file
                saved_path = default_storage.save(file_path, ContentFile(image_file.read()))
                file_paths.append(default_storage.url(saved_path))
        
        return file_paths
    except Exception as e:
        logger.error(f"AnnouncementView : UploadImages : {str(e)}")
        raise e
            
def get_user_id_from_token(request):
    """
    Extract user ID from JWT token in the request header.
    Returns user_id if found, None otherwise.
    """
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None
        
        # Extract token from "Bearer <token>"
        parts = auth_header.split(' ')
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        
        token = parts[1]
        access_token = AccessToken(token)
        user_id = access_token.get('user_id')
        return user_id
        
    except (TokenError, InvalidToken, Exception) as e:
        logger.error(f"Error extracting user ID from token: {str(e)}")
        return None   