import json
import logging
from datetime import datetime
import uuid
from django.db.models import OuterRef, Subquery, Count
from .models import *
from django.db import connection
from .utils import *
from rest_framework_simplejwt.tokens import AccessToken
from datetime import timedelta
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


logger = logging.getLogger(__name__)

# Constants
CLASS_STATUS_ACTIVE = 1
CLASS_STATUS_COMPLETED = 2
CLASS_STATUS_CANCEL = 3

def get_user_type(user_id):
    """Get user type by user ID"""
    try:
        user = User.objects.get(id=user_id)
        return user.type
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
                LEFT JOIN Users u1 ON c.AssignedTeachers = u1.Id
                LEFT JOIN District d ON c.DistrictId = d.Id
                LEFT JOIN VidhanSabha v ON c.VidhanSabhaId = v.Id
                LEFT JOIN Panchayat p ON c.PanchayatId = p.Id
                LEFT JOIN Village vi ON c.VillageId = vi.Id
                LEFT JOIN Users u2 ON c.AssignedRegionalAdmin = u2.Id
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
                INNER JOIN Users u1 ON c.AssignedTeachers = u1.Id
                INNER JOIN District d ON c.DistrictId = d.Id
                INNER JOIN VidhanSabha v ON c.VidhanSabhaId = v.Id
                INNER JOIN Panchayat p ON c.PanchayatId = p.Id
                LEFT JOIN Village vi ON c.VillageId = vi.Id
                LEFT JOIN Users u2 ON c.AssignedRegionalAdmin = u2.Id
                WHERE c.AssignedRegionalAdmin = %s
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
                (SELECT COUNT(*) FROM Student s WHERE s.CenterId = c.Id) as TotalStudents,
                c.AssignedTeachers as TeacherId
            FROM Center c
            LEFT JOIN District d ON c.DistrictId = d.Id
            LEFT JOIN VidhanSabha v ON c.VidhanSabhaId = v.Id
            LEFT JOIN Panchayat p ON c.PanchayatId = p.Id
            LEFT JOIN Village vi ON c.VillageId = vi.Id
            LEFT JOIN Users u ON c.AssignedRegionalAdmin = u.Id
            WHERE c.Id = %s
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
                        WHERE Id = %s
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
            LEFT JOIN District d ON c.DistrictId = d.Id
            LEFT JOIN VidhanSabha v ON c.VidhanSabhaId = v.Id
            LEFT JOIN Panchayat p ON c.PanchayatId = p.Id
            LEFT JOIN Village vi ON c.VillageId = vi.Id
            LEFT JOIN Users u ON c.AssignedRegionalAdmin = u.Id
            WHERE c.AssignedTeachers = %s
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
                        WHERE Id = %s
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
        
        with connection.cursor() as cursor:
            # Get current center status
            center_sql = "SELECT Status FROM Center WHERE Id = %s"
            cursor.execute(center_sql, [center_id])
            center_row = cursor.fetchone()
            
            if not center_row:
                return None
            
            # Update center status
            update_sql = "UPDATE Center SET Status = %s WHERE Id = %s"
            cursor.execute(update_sql, [status, center_id])
            
            # Insert center log
            log_sql = """
                INSERT INTO CenterLog (CenterId, UserId, Reason, CreatedOn)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(log_sql, [center_id, user_id, reason, datetime.now()])
        
        logger.info(f"CenterHelper : UpdateCenterActiveOrDeactive : End")
        return {'centerId': center_id, 'status': status}
        
    except Exception as e:
        logger.error(f"CenterHelper : UpdateCenterActiveOrDeactive : {str(e)}")
        raise e
    
def save_center(center_data):
    """Save or update center with full .NET logic"""
    logger.info(f"CenterHelper : SaveCenter : Started")
    
    try:
        center_id = center_data.get('Id', 0)
        
        with connection.cursor() as cursor:
            if center_id > 0:
                # Update existing center
                # Get existing values to preserve
                select_sql = "SELECT Status, ClassStatus FROM Center WHERE Id = %s"
                cursor.execute(select_sql, [center_id])
                existing = cursor.fetchone()
                
                if existing:
                    update_fields = []
                    update_values = []
                    
                    for key, value in center_data.items():
                        if key != 'Id' and value is not None:
                            column_name = {
                                'CenterName': 'CenterName',
                                'AssignedTeachers': 'AssignedTeachers',
                                'AssignedRegionalAdmin': 'AssignedRegionalAdmin',
                                'StartedDate': 'StartedDate',
                                'VidhanSabhaId': 'VidhanSabhaId',
                                'DistrictId': 'DistrictId',
                                'PanchayatId': 'PanchayatId',
                                'VillageId': 'VillageId'
                            }.get(key, key)
                            
                            update_fields.append(f"{column_name} = %s")
                            update_values.append(value)
                    
                    # Preserve existing Status and ClassStatus
                    update_fields.append("Status = %s")
                    update_values.append(existing[0])
                    
                    update_fields.append("ClassStatus = %s")
                    update_values.append(existing[1])
                    
                    update_values.append(center_id)
                    sql = f"UPDATE Center SET {', '.join(update_fields)} WHERE Id = %s"
                    cursor.execute(sql, update_values)
            else:
                # Insert new center
                created_date = datetime.now()
                
                columns = ['Status', 'ClassStatus', 'CreatedDate']
                values = [1, 0, created_date]
                
                field_mapping = {
                    'CenterGuidId': 'CenterGuidId',
                    'CenterName': 'CenterName',
                    'AssignedTeachers': 'AssignedTeachers',
                    'AssignedRegionalAdmin': 'AssignedRegionalAdmin',
                    'StartedDate': 'StartedDate',
                    'VidhanSabhaId': 'VidhanSabhaId',
                    'DistrictId': 'DistrictId',
                    'PanchayatId': 'PanchayatId',
                    'VillageId': 'VillageId'
                }
                
                for key, column in field_mapping.items():
                    if key in center_data and center_data[key] is not None:
                        columns.append(column)
                        values.append(center_data[key])
                
                placeholders = ', '.join(['%s'] * len(columns))
                sql = f"INSERT INTO Center ({', '.join(columns)}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                
                cursor.execute("SELECT LAST_INSERT_ID()")
                center_id = cursor.fetchone()[0]
                
                # Update assigned teacher status
                assigned_teacher = center_data.get('AssignedTeachers')
                assigned_regional_admin = center_data.get('AssignedRegionalAdmin')
                
                if assigned_teacher:
                    update_user_sql = "UPDATE Users SET AssignedTeacherStatus = 1, AssignedRegionalAdminStatus = 1 WHERE Id = %s"
                    cursor.execute(update_user_sql, [assigned_teacher])
                
                if assigned_regional_admin:
                    update_user_sql = "UPDATE Users SET AssignedTeacherStatus = 1, AssignedRegionalAdminStatus = 1 WHERE Id = %s"
                    cursor.execute(update_user_sql, [assigned_regional_admin])
                
                # Save history of user assign
                if assigned_teacher:
                    insert_assign_sql = """
                        INSERT INTO CenterAssignUser (CenterId, UsersId, Date)
                        VALUES (%s, %s, %s)
                    """
                    cursor.execute(insert_assign_sql, [center_id, assigned_teacher, datetime.now()])
                
                if assigned_regional_admin:
                    insert_assign_sql = """
                        INSERT INTO CenterAssignUser (CenterId, UsersId, Date)
                        VALUES (%s, %s, %s)
                    """
                    cursor.execute(insert_assign_sql, [center_id, assigned_regional_admin, datetime.now()])
        
        return get_center_by_id(center_id)
        
    except Exception as e:
        logger.error(f"CenterHelper : SaveCenter : {str(e)}")
        raise e


# TECHERS SECTION ----------------------------------------------------------
def get_all_teachers(userId):
    """Get all teachers with optional filtering by userId"""
    logger.info(f"UserHelper : GetRegisteredTeachers : Started")
    
    try:
        users = []
        
        if userId == 0:
            # Get all teachers (Type == 3 and Status == True)
            sql = """
                SELECT 
                    u.Id,
                    u.Name,
                    u.AssignedTeacherStatus,
                    u.PhoneNumber,
                    u.Picture
                FROM Users u
                WHERE u.Type = 3 AND u.Status = 1
                ORDER BY u.Name
            """
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                for row in rows:
                    users.append(dict(zip(columns, row)))
        else:
            # Get teachers assigned to centers under this regional admin
            sql = """
                SELECT 
                    u.Id,
                    u.Name,
                    u.AssignedTeacherStatus,
                    u.PhoneNumber,
                    u.Picture
                FROM Users u
                WHERE u.Type = 3 
                    AND u.Status = 1
                    AND u.Id IN (
                        SELECT DISTINCT c.AssignedTeachers 
                        FROM Center c 
                        WHERE c.AssignedRegionalAdmin = %s
                    )
                ORDER BY u.Name
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [userId])
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                for row in rows:
                    users.append(dict(zip(columns, row)))
        
        # Convert to TeacherDto format
        result = []
        for user in users:
            teacher_dto = {
                'id': user.get('Id'),
                'name': user.get('Name'),
                'profile': user.get('Picture'),
                'phoneNumber': user.get('PhoneNumber'),
                'assigned': user.get('AssignedTeacherStatus') if user.get('AssignedTeacherStatus') is not None else False
            }
            result.append(teacher_dto)
        
        logger.info(f"UserHelper : GetRegisteredTeachers : End")
        return result
        
    except Exception as e:
        logger.error(f"UserHelper : GetRegisteredTeachers : {str(e)}")
        raise e
    


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
            WHERE u.Type = 2
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



# USER SECTION---------------------------------------------------------
def login_user(mobile_number, password):
    """Authenticate user by mobile number and password"""
    logger.info(f"UserHelper : LoginUser : Started")
    
    try:
        hashed_password = hash_password(password)
        
        sql = """
            SELECT 
                u.Id,
                u.EnrolmentRollId,
                u.Password,
                u.Name,
                u.Token,
                u.DeviceId,
                u.Type,
                u.Age,
                u.Gender,
                u.Contact,
                u.Status,
                u.DateOfBirth,
                u.Email,
                u.PhoneNumber,
                u.Picture,
                u.WhatsApp,
                u.LastLoginTime,
                u.FullAddress,
                u.RoleId,
                u.CreatedOn,
                u.EnrollmentDate,
                u.GuardianName,
                u.GuardianNumber,
                u.Education,
                u.CreatedBy,
                u.VidhanSabhaId,
                u.DistrictId,
                u.VillageId,
                u.PanchayatId,
                u.AssignedTeacherStatus,
                u.AssignedRegionalAdminStatus
            FROM Users u
            WHERE u.PhoneNumber = %s AND u.Password = %s
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql, [mobile_number, hashed_password])
            row = cursor.fetchone()
            
            if row:
                columns = [col[0] for col in cursor.description]
                user_dict = dict(zip(columns, row))
                
                # Update last login time
                current_time = datetime.now().strftime('%m/%d/%Y %I:%M:%S %p')
                update_sql = """
                    UPDATE Users 
                    SET LastLoginTime = %s 
                    WHERE Id = %s
                """
                cursor.execute(update_sql, [current_time, user_dict.get('Id')])
                
                # Get updated user
                cursor.execute(sql, [mobile_number, hashed_password])
                row = cursor.fetchone()
                if row:
                    user_dict = dict(zip(columns, row))
                
                # Generate token
                token = AccessToken()
                token['user_id'] = user_dict.get('Id')
                token['user_type'] = user_dict.get('Type')
                token['mobile_number'] = mobile_number
                token['name'] = user_dict.get('Name') or mobile_number
                token.set_exp(lifetime=timedelta(days=30))
                
                # Convert Status from 1/0 to True/False
                status_value = user_dict.get('Status')
                if status_value is not None:
                    status_value = bool(status_value)
                
                assigned_teacher_status = user_dict.get('AssignedTeacherStatus')
                if assigned_teacher_status is not None:
                    assigned_teacher_status = bool(assigned_teacher_status)
                
                assigned_regional_admin_status = user_dict.get('AssignedRegionalAdminStatus')
                if assigned_regional_admin_status is not None:
                    assigned_regional_admin_status = bool(assigned_regional_admin_status)
                
                # Build response matching .NET exactly
                response_data = {
                    "id": user_dict.get('Id'),
                    "enrolmentRollId": user_dict.get('EnrolmentRollId'),
                    "password": None,
                    "name": user_dict.get('Name'),
                    "token": str(token),
                    "deviceId": user_dict.get('DeviceId'),
                    "type": user_dict.get('Type'),
                    "age": user_dict.get('Age'),
                    "gender": user_dict.get('Gender'),
                    "contact": user_dict.get('Contact'),
                    "status": status_value,
                    "dateOfBirth": user_dict.get('DateOfBirth'),
                    "email": user_dict.get('Email'),
                    "phoneNumber": user_dict.get('PhoneNumber'),
                    "picture": user_dict.get('Picture'),
                    "whatsApp": user_dict.get('WhatsApp'),
                    "lastLoginTime": user_dict.get('LastLoginTime'),
                    "fullAddress": user_dict.get('FullAddress'),
                    "roleId": user_dict.get('RoleId'),
                    "createdOn": user_dict.get('CreatedOn'),
                    "enrollmentDate": user_dict.get('EnrollmentDate'),
                    "guardianName": user_dict.get('GuardianName'),
                    "guardianNumber": user_dict.get('GuardianNumber'),
                    "education": user_dict.get('Education'),
                    "createdBy": user_dict.get('CreatedBy'),
                    "vidhanSabhaId": user_dict.get('VidhanSabhaId'),
                    "districtId": user_dict.get('DistrictId'),
                    "villageId": user_dict.get('VillageId'),
                    "panchayatId": user_dict.get('PanchayatId'),
                    "assignedTeacherStatus": assigned_teacher_status,
                    "assignedRegionalAdminStatus": assigned_regional_admin_status,
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
                
                logger.info(f"UserHelper : LoginUser : End")
                return response_data
        
        return None
        
    except Exception as e:
        logger.error(f"UserHelper : LoginUser : {str(e)}")
        raise e
    
    
def save_user(user_data):
    """Save or update user"""
    logger.info(f"UserHelper : SaveLogin : Started")
    
    try:
        user_id = int(user_data.get('Id', 0))
        print(f"Saving user with ID: {user_id}")
        
        with connection.cursor() as cursor:
            if user_id > 0:
                print("if")
                # Get existing user to preserve values
                select_sql = """
                    SELECT 
                        Id, EnrolmentRollId, Password, Type, Status, 
                        CreatedOn, AssignedTeacherStatus, AssignedRegionalAdminStatus
                    FROM Users 
                    WHERE Id = %s
                """
                cursor.execute(select_sql, [user_id])
                existing = cursor.fetchone()
                
                if existing:
                    enrolment_roll_id = existing[1]
                    existing_password = existing[2]
                    user_type = existing[3]
                    existing_status = existing[4]
                    existing_created_on = existing[5]
                    
                    update_fields = []
                    update_values = []
                    
                    # Always add UpdatedOn and UpdatedBy for any update
                    update_fields.append("UpdatedOn = %s")
                    update_values.append(datetime.now())
                    
                    # Use CreatedBy from request as UpdatedBy
                    created_by = user_data.get('CreatedBy')
                    if created_by:
                        update_fields.append("UpdatedBy = %s")
                        update_values.append(created_by)
                    else:
                        # If CreatedBy is not provided, use the user's own ID as fallback
                        update_fields.append("UpdatedBy = %s")
                        update_values.append(user_id)
                    
                    # If Type == 1 (SuperAdmin) - can change anything
                    if user_type == 1:
                        # SuperAdmin can change password
                        if user_data.get('Password') and user_data['Password'] != existing_password:
                            update_fields.append("Password = %s")
                            update_values.append(user_data['Password'])
                        
                        # SuperAdmin can change all fields
                        field_mapping = {
                            'Name': 'Name',
                            'Token': 'Token',
                            'Email': 'Email',
                            'Age': 'Age',
                            'Gender': 'Gender',
                            'Contact': 'Contact',
                            'DateOfBirth': 'DateOfBirth',
                            'PhoneNumber': 'PhoneNumber',
                            'Picture': 'Picture',
                            'WhatsApp': 'WhatsApp',
                            'LastLoginTime': 'LastLoginTime',
                            'FullAddress': 'FullAddress',
                            'RoleId': 'RoleId',
                            'DeviceId': 'DeviceId',
                            'Education': 'Education',
                            'VidhanSabhaId': 'VidhanSabhaId',
                            'DistrictId': 'DistrictId',
                            'VillageId': 'VillageId',
                            'PanchayatId': 'PanchayatId',
                            'GuardianName': 'GuardianName',
                            'GuardianNumber': 'GuardianNumber',
                            'AssignedTeacherStatus': 'AssignedTeacherStatus',
                            'AssignedRegionalAdminStatus': 'AssignedRegionalAdminStatus',
                            'CreatedBy': 'CreatedBy',
                        }
                        
                        for key, column in field_mapping.items():
                            if key in user_data and user_data[key] is not None:
                                update_fields.append(f"{column} = %s")
                                update_values.append(user_data[key])
                    else:
                        # Non-superadmin: preserve EnrolmentRollId, Password, Status, CreatedOn
                        # Only update specific fields from ConvertUpdateUsertoToUser
                        if user_data.get('DateOfBirth'):
                            update_fields.append("DateOfBirth = %s")
                            update_values.append(user_data['DateOfBirth'])
                        
                        if user_data.get('GuardianName'):
                            update_fields.append("GuardianName = %s")
                            update_values.append(user_data['GuardianName'])
                        
                        if user_data.get('GuardianNumber'):
                            update_fields.append("GuardianNumber = %s")
                            update_values.append(user_data['GuardianNumber'])
                        
                        if user_data.get('Email'):
                            update_fields.append("Email = %s")
                            update_values.append(user_data['Email'])
                        
                        if user_data.get('PhoneNumber'):
                            update_fields.append("PhoneNumber = %s")
                            update_values.append(user_data['PhoneNumber'])
                        
                        if user_data.get('Name'):
                            update_fields.append("Name = %s")
                            update_values.append(user_data['Name'])
                        
                        # Preserve existing values for these fields
                        update_fields.append("EnrolmentRollId = %s")
                        update_values.append(enrolment_roll_id)
                        
                        update_fields.append("Password = %s")
                        update_values.append(existing_password)
                        
                        update_fields.append("Status = %s")
                        update_values.append(existing_status)
                        
                        update_fields.append("CreatedOn = %s")
                        update_values.append(existing_created_on)
                        
                        # Update PanchayatId for teachers (Type == 3)
                        print("user_type", user_type)
                        list_of_panchayat_ids = user_data.get('ListOfPanchayatIds')
                        if user_type == 3 and list_of_panchayat_ids:
                            if isinstance(list_of_panchayat_ids, str):
                                panchayat_list = [int(x.strip()) for x in list_of_panchayat_ids.split(',') if x.strip()]
                            else:
                                panchayat_list = list_of_panchayat_ids if isinstance(list_of_panchayat_ids, list) else []
                                
                            print("panchayat_list", panchayat_list)

                            if len(panchayat_list) == 1:
                                update_fields.append("PanchayatId = %s")
                                update_values.append(panchayat_list[0])

                        # Update DistrictId for teachers if provided
                        if user_type == 3 and user_data.get('DistrictId') is not None:
                            update_fields.append("DistrictId = %s")
                            update_values.append(user_data['DistrictId'])

                        # Update VidhanSabhaId for teachers if provided
                        if user_type == 3 and user_data.get('VidhanSabhaId') is not None:
                            update_fields.append("VidhanSabhaId = %s")
                            update_values.append(user_data['VidhanSabhaId'])

                        # Update VillageId for teachers if provided
                        if user_type == 3 and user_data.get('VillageId') is not None:
                            update_fields.append("VillageId = %s")
                            update_values.append(user_data['VillageId'])
                    
                    # Handle ListOfPanchayatIds for RegionalAdmin
                    if user_type == 2:  # RegionalAdmin
                        list_of_panchayat_ids = user_data.get('ListOfPanchayatIds')
                        if list_of_panchayat_ids:
                            if isinstance(list_of_panchayat_ids, str):
                                panchayat_list = [int(x.strip()) for x in list_of_panchayat_ids.split(',') if x.strip()]
                            else:
                                panchayat_list = list_of_panchayat_ids if isinstance(list_of_panchayat_ids, list) else []
                            
                            if panchayat_list:
                                # Delete existing RegionalAdminPanchayat records
                                cursor.execute("DELETE FROM RegionalAdminPanchayat WHERE UsersId = %s", [user_id])
                                
                                # Insert new records
                                for panchayat_id in panchayat_list:
                                    cursor.execute("SELECT Name FROM Panchayat WHERE Id = %s", [panchayat_id])
                                    panchayat_row = cursor.fetchone()
                                    panchayat_name = panchayat_row[0] if panchayat_row else None
                                    
                                    if panchayat_name:
                                        insert_sql = """
                                            INSERT INTO RegionalAdminPanchayat (UsersId, PanchayatId, PanchayatName)
                                            VALUES (%s, %s, %s)
                                        """
                                        cursor.execute(insert_sql, [user_id, panchayat_id, panchayat_name])
                    
                    if update_fields:
                        update_values.append(user_id)
                        sql = f"UPDATE Users SET {', '.join(update_fields)} WHERE Id = %s"
                        cursor.execute(sql, update_values)
            else:
                print("else")
                # Insert new user
                name = user_data.get('Name', '')
                date_of_birth = user_data.get('DateOfBirth', '')
                gender = user_data.get('Gender', '')
                
                enrolment_roll_id = f"{name[:2]}-{date_of_birth}-"
                if gender and gender.lower() == 'male':
                    enrolment_roll_id += 'M'
                else:
                    enrolment_roll_id += 'F'
                
                created_on = datetime.now()
                
                # Start with required columns and values
                columns = ['EnrolmentRollId', 'Status', 'CreatedOn']
                values = [enrolment_roll_id, 1, created_on]
                
                # Map fields to column names
                field_mapping = {
                    'Name': 'Name',
                    'Password': 'Password',
                    'Token': 'Token',
                    'Email': 'Email',
                    'Type': 'Type',
                    'Age': 'Age',
                    'Gender': 'Gender',
                    'Contact': 'Contact',
                    'DateOfBirth': 'DateOfBirth',
                    'PhoneNumber': 'PhoneNumber',
                    'Picture': 'Picture',
                    'WhatsApp': 'WhatsApp',
                    'LastLoginTime': 'LastLoginTime',
                    'FullAddress': 'FullAddress',
                    'RoleId': 'RoleId',
                    'DeviceId': 'DeviceId',
                    'Education': 'Education',
                    'VidhanSabhaId': 'VidhanSabhaId',
                    'DistrictId': 'DistrictId',
                    'VillageId': 'VillageId',
                    'PanchayatId': 'PanchayatId',
                    'GuardianName': 'GuardianName',
                    'GuardianNumber': 'GuardianNumber',
                    'AssignedTeacherStatus': 'AssignedTeacherStatus',
                    'AssignedRegionalAdminStatus': 'AssignedRegionalAdminStatus',
                    'CreatedBy': 'CreatedBy',
                }
                
                for key, column in field_mapping.items():
                    if key in user_data and user_data[key] is not None:
                        columns.append(column)
                        values.append(user_data[key])
                
                user_type = user_data.get('Type')
                
                # Handle ListOfPanchayatIds for Teacher
                if user_type == 3:  # Teacher
                    list_of_panchayat_ids = user_data.get('ListOfPanchayatIds')
                    print("list_of_panchayat_ids", list_of_panchayat_ids)
                    if list_of_panchayat_ids:
                        if isinstance(list_of_panchayat_ids, str):
                            panchayat_list = [int(x.strip()) for x in list_of_panchayat_ids.split(',') if x.strip()]
                        else:
                            panchayat_list = list_of_panchayat_ids if isinstance(list_of_panchayat_ids, list) else []
                        
                        if len(panchayat_list) == 1:
                            columns.append('PanchayatId')
                            values.append(panchayat_list[0])
                
                placeholders = ', '.join(['%s'] * len(columns))
                sql = f"INSERT INTO Users ({', '.join(columns)}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                print("sql", sql, values)
                
                cursor.execute("SELECT LAST_INSERT_ID()")
                user_id = cursor.fetchone()[0]
                
                # Handle RegionalAdminPanchayat for RegionalAdmin
                if user_type == 2:  # RegionalAdmin
                    list_of_panchayat_ids = user_data.get('ListOfPanchayatIds')
                    if list_of_panchayat_ids:
                        if isinstance(list_of_panchayat_ids, str):
                            panchayat_list = [int(x.strip()) for x in list_of_panchayat_ids.split(',') if x.strip()]
                        else:
                            panchayat_list = list_of_panchayat_ids if isinstance(list_of_panchayat_ids, list) else []
                        
                        for panchayat_id in panchayat_list:
                            cursor.execute("SELECT Name FROM Panchayat WHERE Id = %s", [panchayat_id])
                            panchayat_row = cursor.fetchone()
                            panchayat_name = panchayat_row[0] if panchayat_row else None
                            
                            if panchayat_name:
                                insert_sql = """
                                    INSERT INTO RegionalAdminPanchayat (UsersId, PanchayatId, PanchayatName)
                                    VALUES (%s, %s, %s)
                                """
                                cursor.execute(insert_sql, [user_id, panchayat_id, panchayat_name])
        
        return get_user_by_id(user_id)
        
    except Exception as e:
        logger.error(f"UserHelper : SaveLogin : {str(e)}")
        raise e
        
    except Exception as e:
        logger.error(f"UserHelper : SaveLogin : {str(e)}")
        raise e

def get_user_by_id(user_id):
    """Get user by ID matching .NET response structure exactly"""
    logger.info(f"UserHelper : GetUserById : Started")
    
    try:
        sql = """
            SELECT 
                u.Id,
                u.EnrolmentRollId,
                u.Name,
                u.Email,
                u.Type,
                u.Age,
                u.Gender,
                u.Contact,
                u.Status,
                u.DateOfBirth,
                u.PhoneNumber,
                u.Picture,
                u.WhatsApp,
                u.LastLoginTime,
                u.FullAddress,
                u.Education,
                u.CreatedOn,
                u.EnrollmentDate,
                u.CreatedBy,
                u.VidhanSabhaId,
                u.DistrictId,
                u.VillageId,
                u.PanchayatId,
                u.AssignedTeacherStatus,
                u.AssignedRegionalAdminStatus,
                u.GuardianName,
                u.GuardianNumber,
                d.Name as DistrictName,
                v.Name as VidhanSabhaName,
                vi.Name as VillageName,
                p.Name as PanchayatName
            FROM Users u
            LEFT JOIN District d ON u.DistrictId = d.Id
            LEFT JOIN VidhanSabha v ON u.VidhanSabhaId = v.Id
            LEFT JOIN Panchayat p ON u.PanchayatId = p.Id
            LEFT JOIN Village vi ON u.VillageId = vi.Id
            WHERE u.Id = %s
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql, [user_id])
            row = cursor.fetchone()
            
            if row:
                columns = [col[0] for col in cursor.description]
                user_dict = dict(zip(columns, row))
                
                user_type = user_dict.get('Type')
                
                # Super Admin (Type 1) - only basic fields
                if user_type == 1:
                    response = {
                        'id': user_dict.get('Id'),
                        'enrolmentRollId': user_dict.get('EnrolmentRollId'),
                        'name': user_dict.get('Name'),
                        'email': user_dict.get('Email'),
                        'type': user_dict.get('Type'),
                        'age': user_dict.get('Age'),
                        'gender': user_dict.get('Gender'),
                        'contact': user_dict.get('Contact'),
                        'status': bool(user_dict.get('Status')) if user_dict.get('Status') is not None else None,
                        'dateOfBirth': user_dict.get('DateOfBirth'),
                        'phoneNumber': user_dict.get('PhoneNumber'),
                        'picture': user_dict.get('Picture'),
                        'whatsApp': user_dict.get('WhatsApp'),
                        'lastLoginTime': user_dict.get('LastLoginTime'),
                        'fullAddress': user_dict.get('FullAddress'),
                        'createdOn': user_dict.get('CreatedOn').strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] if user_dict.get('CreatedOn') else None,
                        'enrollmentDate': user_dict.get('EnrollmentDate').strftime('%Y-%m-%dT%H:%M:%S') if user_dict.get('EnrollmentDate') else None,
                        'createdBy': user_dict.get('CreatedBy')
                    }
                    return response
                
                # Regional Admin (Type 2)
                elif user_type == 2:
                    # Get list of panchayats
                    panchayat_sql = """
                        SELECT 
                            rp.PanchayatId as Id,
                            p.PanchayatGuidId,
                            p.Name,
                            p.Status,
                            p.CreatedOn,
                            p.CreatedBy,
                            p.DistrictId,
                            p.VidhanSabhaId
                        FROM RegionalAdminPanchayat rp
                        INNER JOIN Panchayat p ON rp.PanchayatId = p.Id
                        WHERE rp.UsersId = %s
                    """
                    cursor.execute(panchayat_sql, [user_id])
                    panchayat_rows = cursor.fetchall()
                    
                    list_of_panchayat = []
                    if panchayat_rows:
                        panchayat_columns = [col[0] for col in cursor.description]
                        for row in panchayat_rows:
                            panchayat_dict = dict(zip(panchayat_columns, row))
                            list_of_panchayat.append({
                                'id': panchayat_dict.get('Id'),
                                'panchayatGuidId': panchayat_dict.get('PanchayatGuidId') or '00000000-0000-0000-0000-000000000000',
                                'name': panchayat_dict.get('Name'),
                                'status': panchayat_dict.get('Status'),
                                'createdOn': panchayat_dict.get('CreatedOn'),
                                'createdBy': panchayat_dict.get('CreatedBy'),
                                'districtId': panchayat_dict.get('DistrictId') or 0,
                                'vidhanSabhaId': panchayat_dict.get('VidhanSabhaId') or 0
                            })
                    
                    # Get list of centers
                    centers_sql = """
                        SELECT 
                            c.Id,
                            c.CenterGuidId,
                            c.CenterName,
                            c.AssignedTeachers,
                            c.AssignedRegionalAdmin,
                            c.StartedDate,
                            c.VidhanSabhaId,
                            c.DistrictId,
                            c.PanchayatId,
                            c.VillageId
                        FROM Center c
                        WHERE c.AssignedRegionalAdmin = %s
                    """
                    cursor.execute(centers_sql, [user_id])
                    centers_rows = cursor.fetchall()
                    
                    list_of_centers = []
                    if centers_rows:
                        centers_columns = [col[0] for col in cursor.description]
                        for row in centers_rows:
                            center_dict = dict(zip(centers_columns, row))
                            list_of_centers.append({
                                'id': center_dict.get('Id'),
                                'centerGuidId': center_dict.get('CenterGuidId'),
                                'centerName': center_dict.get('CenterName'),
                                'assignedTeachers': center_dict.get('AssignedTeachers'),
                                'assignedRegionalAdmin': center_dict.get('AssignedRegionalAdmin'),
                                'startedDate': center_dict.get('StartedDate'),
                                'vidhanSabhaId': center_dict.get('VidhanSabhaId') or 0,
                                'districtId': center_dict.get('DistrictId') or 0,
                                'panchayatId': center_dict.get('PanchayatId') or 0,
                                'villageId': center_dict.get('VillageId')
                            })
                    
                    response = {
                        'id': user_dict.get('Id'),
                        'enrolmentRollId': user_dict.get('EnrolmentRollId'),
                        'name': user_dict.get('Name'),
                        'email': user_dict.get('Email'),
                        'type': user_dict.get('Type'),
                        'age': user_dict.get('Age'),
                        'gender': user_dict.get('Gender'),
                        'contact': user_dict.get('Contact'),
                        'status': bool(user_dict.get('Status')) if user_dict.get('Status') is not None else None,
                        'dateOfBirth': user_dict.get('DateOfBirth'),
                        'phoneNumber': user_dict.get('PhoneNumber'),
                        'picture': user_dict.get('Picture'),
                        'whatsApp': user_dict.get('WhatsApp'),
                        'lastLoginTime': user_dict.get('LastLoginTime'),
                        'fullAddress': user_dict.get('FullAddress'),
                        'education': user_dict.get('Education'),
                        'createdOn': user_dict.get('CreatedOn').strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] if user_dict.get('CreatedOn') else None,
                        'enrollmentDate': user_dict.get('EnrollmentDate').strftime('%Y-%m-%dT%H:%M:%S') if user_dict.get('EnrollmentDate') else None,
                        'createdBy': user_dict.get('CreatedBy'),
                        'vidhanSabhaId': user_dict.get('VidhanSabhaId'),
                        'districtId': user_dict.get('DistrictId'),
                        'villageId': user_dict.get('VillageId'),
                        'assignedTeacherStatus': user_dict.get('AssignedTeacherStatus'),
                        'assignedRegionalAdminStatus': user_dict.get('AssignedRegionalAdminStatus'),
                        'guardianName': user_dict.get('GuardianName'),
                        'guardianNumber': user_dict.get('GuardianNumber'),
                        'districtName': user_dict.get('DistrictName'),
                        'vidhanSabhaName': user_dict.get('VidhanSabhaName'),
                        'villageName': user_dict.get('VillageName') or '',
                        'listOfPanchayat': list_of_panchayat,
                        'listOfCenters': list_of_centers,
                        'assignedDate': None
                    }
                    return response
                
                # Teacher (Type 3)
                elif user_type == 3:
                    # Get center details
                    center_sql = """
                        SELECT 
                            c.Id,
                            c.CenterGuidId,
                            c.CenterName,
                            c.ClassStatus,
                            c.Status,
                            c.CreatedDate,
                            c.StartedDate,
                            c.AssignedTeachers,
                            c.AssignedRegionalAdmin,
                            c.VidhanSabhaId,
                            c.DistrictId,
                            c.PanchayatId,
                            c.VillageId
                        FROM Center c
                        WHERE c.AssignedTeachers = %s
                    """
                    cursor.execute(center_sql, [user_id])
                    center_row = cursor.fetchone()
                    
                    center_data = None
                    if center_row:
                        center_columns = [col[0] for col in cursor.description]
                        center_dict = dict(zip(center_columns, center_row))
                        center_data = {
                            'id': center_dict.get('Id'),
                            'centerGuidId': center_dict.get('CenterGuidId'),
                            'centerName': center_dict.get('CenterName'),
                            'classStatus': bool(center_dict.get('ClassStatus')) if center_dict.get('ClassStatus') is not None else None,
                            'status': bool(center_dict.get('Status')) if center_dict.get('Status') is not None else None,
                            'createdDate': center_dict.get('CreatedDate'),
                            'startedDate': center_dict.get('StartedDate'),
                            'assignedTeachers': center_dict.get('AssignedTeachers'),
                            'assignedRegionalAdmin': center_dict.get('AssignedRegionalAdmin'),
                            'vidhanSabhaId': center_dict.get('VidhanSabhaId') or 0,
                            'districtId': center_dict.get('DistrictId') or 0,
                            'panchayatId': center_dict.get('PanchayatId') or 0,
                            'villageId': center_dict.get('VillageId'),
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
                    
                    response = {
                        'id': user_dict.get('Id'),
                        'enrolmentRollId': user_dict.get('EnrolmentRollId'),
                        'name': user_dict.get('Name'),
                        'email': user_dict.get('Email'),
                        'type': user_dict.get('Type'),
                        'age': user_dict.get('Age'),
                        'gender': user_dict.get('Gender'),
                        'contact': user_dict.get('Contact'),
                        'status': bool(user_dict.get('Status')) if user_dict.get('Status') is not None else None,
                        'dateOfBirth': user_dict.get('DateOfBirth'),
                        'phoneNumber': user_dict.get('PhoneNumber'),
                        'picture': user_dict.get('Picture'),
                        'whatsApp': user_dict.get('WhatsApp'),
                        'lastLoginTime': user_dict.get('LastLoginTime'),
                        'fullAddress': user_dict.get('FullAddress'),
                        'education': user_dict.get('Education'),
                        'createdOn': user_dict.get('CreatedOn').strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] if user_dict.get('CreatedOn') else None,
                        'enrollmentDate': user_dict.get('EnrollmentDate').strftime('%Y-%m-%dT%H:%M:%S') if user_dict.get('EnrollmentDate') else None,
                        'createdBy': user_dict.get('CreatedBy'),
                        'vidhanSabhaId': user_dict.get('VidhanSabhaId'),
                        'districtId': user_dict.get('DistrictId'),
                        'villageId': user_dict.get('VillageId'),
                        'panchayatId': user_dict.get('PanchayatId'),
                        'assignedTeacherStatus': user_dict.get('AssignedTeacherStatus'),
                        'assignedRegionalAdminStatus': user_dict.get('AssignedRegionalAdminStatus'),
                        'guardianName': user_dict.get('GuardianName'),
                        'guardianNumber': user_dict.get('GuardianNumber'),
                        'districtName': user_dict.get('DistrictName'),
                        'vidhanSabhaName': user_dict.get('VidhanSabhaName'),
                        'villageName': user_dict.get('VillageName'),
                        'panchayatName': user_dict.get('PanchayatName'),
                        'center': center_data,
                        'centerEnrollmentDate': None,
                        'assignedDate': None
                    }
                    return response
        
        return None
        
    except Exception as e:
        logger.error(f"UserHelper : GetUserById : {str(e)}")
        raise e

def update_user_device_id(user_id, device_id):
    """Update user device ID"""
    logger.info(f"UserHelper : UpdateDeviceId : Started")
    
    try:
        sql = """
            UPDATE Users 
            SET DeviceId = %s 
            WHERE Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [device_id, user_id])
        
        return get_user_by_id(user_id)
        
    except Exception as e:
        logger.error(f"UserHelper : UpdateDeviceId : {str(e)}")
        raise e

def update_user_password(user_id, new_password):
    """Update user password"""
    logger.info(f"UserHelper : UpdatePassword : Started")
    
    try:
        hashed_password = hash_password(new_password)
        sql = """
            UPDATE Users 
            SET Password = %s 
            WHERE Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [hashed_password, user_id])
        
        return get_user_by_id(user_id)
        
    except Exception as e:
        logger.error(f"UserHelper : UpdatePassword : {str(e)}")
        raise e

def get_user_detail_by_phone(phone_number):
    """Get user details by phone number"""
    logger.info(f"UserHelper : GetUserDetailByPhoneNumber : Started")
    
    try:
        sql = """
            SELECT 
                Id,
                Name,
                PhoneNumber,
                Email,
                Type,
                Status
            FROM Users
            WHERE PhoneNumber = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [phone_number])
            row = cursor.fetchone()
            
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        
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
            'Users': ('Users', 'Name'),
            'Student': ('Student', 'FullName'),
            'District': ('District', 'Name'),
            'Panchayat': ('Panchayat', 'Name'),
            'VidhanSabha': ('VidhanSabha', 'Name'),
            'Village': ('Village', 'Name'),
            'Center': ('Center', 'CenterName'),
            'School': ('School', 'SchoolName'),
            'Class': ('Class', 'Name'),
            'Teacher': ('Teacher', 'FullName')
        }
        
        if search_type in search_map:
            table, field = search_map[search_type]
            sql = f"""
                SELECT * 
                FROM {table}
                WHERE {field} LIKE %s
                LIMIT 25
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [f'%{query_string}%'])
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                for row in rows:
                    results.append(dict(zip(columns, row)))
        
        logger.info(f"UserHelper : SearchData : End")
        return results
        
    except Exception as e:
        logger.error(f"UserHelper : SearchData : {str(e)}")
        raise e

#---------------------------------------------------------
# Class APIs Helper Functions
#---------------------------------------------------------

def save_class(class_data):
    """Save a new class"""
    logger.info(f"ClassHelper : SaveClass : Started")
    
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
        """
        with connection.cursor() as cursor:
            cursor.execute(check_sql, [class_enrolment_id, today, center_id])
            existing = cursor.fetchone()
            
            if existing:
                return None
            
            # Insert new class
            insert_sql = """
                INSERT INTO Class (
                    ClassEnrolmentId, Name, CenterId, UsersId, 
                    TotalStudents, AvilableStudents, StartedDate, 
                    Status, SubStatus
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                0   # SubStatus
            ])
            
            # Get the inserted ID
            cursor.execute("SELECT LAST_INSERT_ID()")
            class_id = cursor.fetchone()[0]
            
            # Update center class status
            update_center_sql = "UPDATE Center SET ClassStatus = 1 WHERE Id = %s"
            cursor.execute(update_center_sql, [center_id])
        
        # Get the saved class
        return get_class_by_id(class_id)
        
    except Exception as e:
        logger.error(f"ClassHelper : SaveClass : {str(e)}")
        raise e

def get_class_by_id(class_id):
    """Get class by ID"""
    try:
        sql = """
            SELECT 
                Id, ClassEnrolmentId, Name, CenterId, UsersId,
                TotalStudents, AvilableStudents, StartedDate,
                EndDate, Status, SubStatus, Reason, CancelBy, CancelDate
            FROM Class
            WHERE Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [class_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.error(f"ClassHelper : get_class_by_id : {str(e)}")
        raise e

def cancel_class(class_data):
    """Cancel a class"""
    logger.info(f"ClassHelper : CancelClass : Started")
    
    try:
        class_id = class_data.get('id')
        reason = class_data.get('reason')
        cancel_by = class_data.get('cancelBy')
        
        sql = """
            UPDATE Class 
            SET Reason = %s, CancelBy = %s, CancelDate = %s, Status = 3
            WHERE Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [reason, cancel_by, datetime.now(), class_id])
        
        return get_class_by_id(class_id)
        
    except Exception as e:
        logger.error(f"ClassHelper : CancelClass : {str(e)}")
        raise e

def update_end_class_time(class_id):
    """Update end class time"""
    logger.info(f"ClassHelper : UpdateEndClassTime : Started")
    
    try:
        with connection.cursor() as cursor:
            # Get class data
            class_sql = "SELECT CenterId FROM Class WHERE Id = %s"
            cursor.execute(class_sql, [class_id])
            row = cursor.fetchone()
            
            if not row:
                return None
            
            center_id = row[0]
            
            # Update class
            update_sql = """
                UPDATE Class 
                SET EndDate = %s, Status = 2
                WHERE Id = %s
            """
            cursor.execute(update_sql, [datetime.now(), class_id])
            
            # Update student active class status
            student_sql = """
                UPDATE Student s
                SET s.ActiveClassStatus = 0
                WHERE s.CenterId = %s 
                AND s.Id IN (
                    SELECT DISTINCT sa.StudentId 
                    FROM StudentAttendance sa 
                    WHERE sa.CenterId = %s
                )
            """
            cursor.execute(student_sql, [center_id, center_id])
        
        return get_class_by_id(class_id)
        
    except Exception as e:
        logger.error(f"ClassHelper : UpdateEndClassTime : {str(e)}")
        raise e

def update_class_sub_status(class_id):
    """Update class sub status"""
    logger.info(f"ClassHelper : UpdateClassSubStatus : Started")
    
    try:
        sql = "UPDATE Class SET SubStatus = 1 WHERE Id = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [class_id])
        
        return get_class_by_id(class_id)
        
    except Exception as e:
        logger.error(f"ClassHelper : UpdateClassSubStatus : {str(e)}")
        raise e

def cancel_class_by_teacher(class_cancel_data):
    """Cancel class by teacher"""
    logger.info(f"ClassHelper : CancelClassByTeacher : Started")
    
    try:
        insert_sql = """
            INSERT INTO ClassCancelByTeacher (
                CenterId, UserId, StartingDate, EndingDate, 
                Reason, CreatedOn
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        with connection.cursor() as cursor:
            cursor.execute(insert_sql, [
                class_cancel_data.get('centerId'),
                class_cancel_data.get('usersId'),
                class_cancel_data.get('startingDate'),
                class_cancel_data.get('endingDate'),
                class_cancel_data.get('reason'),
                datetime.now()
            ])
            
            cursor.execute("SELECT LAST_INSERT_ID()")
            cancel_id = cursor.fetchone()[0]
        
        return {'id': cancel_id}
        
    except Exception as e:
        logger.error(f"ClassHelper : CancelClassByTeacher : {str(e)}")
        raise e

def delete_class_by_teacher_id(class_id):
    """Delete class by teacher ID"""
    logger.info(f"ClassHelper : DeleteClassByTeacherId : Started")
    
    try:
        with connection.cursor() as cursor:
            # Get class to find users_id
            class_sql = "SELECT UsersId FROM Class WHERE Id = %s"
            cursor.execute(class_sql, [class_id])
            row = cursor.fetchone()
            
            if not row:
                return None
            
            users_id = row[0]
            
            # Delete class cancel by teacher
            cursor.execute("DELETE FROM ClassCancelByTeacher WHERE UserId = %s", [users_id])
            
            # Delete student attendance
            cursor.execute("DELETE FROM StudentAttendance WHERE ClassId = %s", [class_id])
            
            # Delete class
            cursor.execute("DELETE FROM Class WHERE Id = %s", [class_id])
        
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
        
        with connection.cursor() as cursor:
            # Check holidays
            holiday_sql = """
                SELECT Name, StartDate, EndDate
                FROM Holidays
                WHERE CenterId = %s 
                AND DATE(StartDate) <= %s 
                AND DATE(EndDate) >= %s
            """
            cursor.execute(holiday_sql, [center_id, today, today])
            holiday_rows = cursor.fetchall()
            
            for row in holiday_rows:
                result['data'].append({
                    'name': row[0],
                    'type': 1,
                    'startedDate': row[1],
                    'endDate': row[2]
                })
            
            # Check class cancel by teacher
            cancel_sql = """
                SELECT Reason, StartingDate, EndingDate
                FROM ClassCancelByTeacher
                WHERE UserId = %s 
                AND DATE(StartingDate) <= %s 
                AND DATE(EndingDate) >= %s
            """
            cursor.execute(cancel_sql, [teacher_id, today, today])
            cancel_rows = cursor.fetchall()
            
            for row in cancel_rows:
                result['data'].append({
                    'name': row[0],
                    'type': 2,
                    'startedDate': row[1],
                    'endDate': row[2]
                })
            
            # Check active class
            active_sql = """
                SELECT Id, Name, SubStatus, StartedDate, EndDate
                FROM Class
                WHERE DATE(StartedDate) = %s 
                AND CenterId = %s 
                AND Status = 1
            """
            cursor.execute(active_sql, [today, center_id])
            active_row = cursor.fetchone()
            
            if active_row:
                result['data'].append({
                    'name': 'Class is going on',
                    'type': 3,
                    'subStatus': active_row[2],
                    'id': active_row[0],
                    'startedDate': active_row[3],
                    'endDate': active_row[4]
                })
            
            # Check completed class
            completed_sql = """
                SELECT Id, StartedDate, EndDate
                FROM Class
                WHERE DATE(StartedDate) = %s 
                AND CenterId = %s 
                AND Status = 2
            """
            cursor.execute(completed_sql, [today, center_id])
            completed_row = cursor.fetchone()
            
            if completed_row:
                result['data'].append({
                    'name': 'Class Ended',
                    'type': 4,
                    'id': completed_row[0],
                    'startedDate': completed_row[1],
                    'endDate': completed_row[2]
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
                return dict(zip(columns, row))
        
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
        if offset == 0 and limit == 0:
            sql = """
                SELECT 
                    Id,
                    DistrictGuidId,
                    Name,
                    Status,
                    CreatedOn,
                    CreatedBy
                FROM District
                ORDER BY Id
            """
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                result = []
                for row in rows:
                    result.append(dict(zip(columns, row)))
                return result
        else:
            sql = """
                SELECT 
                    Id,
                    DistrictGuidId,
                    Name,
                    Status,
                    CreatedOn,
                    CreatedBy
                FROM District
                ORDER BY Id
                LIMIT %s OFFSET %s
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [limit, offset])
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                result = []
                for row in rows:
                    result.append(dict(zip(columns, row)))
                return result
                
    except Exception as e:
        logger.error(f"DistrictHelper : GetAllDistrict : {str(e)}")
        raise e

def save_district(district_data):
    """Save or update district"""
    logger.info(f"DistrictHelper : SaveDistrict : Started")
    
    try:
        district_id = district_data.get('Id', 0)
        
        if district_id > 0:
            # Update existing district
            update_fields = []
            update_values = []
            
            for key, value in district_data.items():
                if key != 'Id' and value is not None:
                    column_name = {
                        'Name': 'Name',
                        'Status': 'Status',
                        'CreatedBy': 'CreatedBy',
                        'DistrictGuidId': 'DistrictGuidId'
                    }.get(key, key)
                    
                    update_fields.append(f"{column_name} = %s")
                    update_values.append(value)
            
            if update_fields:
                update_values.append(district_id)
                sql = f"""
                    UPDATE District 
                    SET {', '.join(update_fields)}
                    WHERE Id = %s
                """
                with connection.cursor() as cursor:
                    cursor.execute(sql, update_values)
        else:
            # Insert new district
            district_guid = str(uuid.uuid4())
            created_on = datetime.now()
            
            sql = """
                INSERT INTO District (
                    DistrictGuidId, Name, Status, CreatedOn, CreatedBy
                ) VALUES (%s, %s, %s, %s, %s)
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [
                    district_guid,
                    district_data.get('Name'),
                    district_data.get('Status'),
                    created_on,
                    district_data.get('CreatedBy')
                ])
                
                cursor.execute("SELECT LAST_INSERT_ID()")
                district_id = cursor.fetchone()[0]
        
        # Get the saved district
        return get_district_by_id(district_id)
        
    except Exception as e:
        logger.error(f"DistrictHelper : SaveDistrict : {str(e)}")
        raise e

def get_district_by_id(district_id):
    """Get district by ID"""
    try:
        sql = """
            SELECT 
                Id,
                DistrictGuidId,
                Name,
                Status,
                CreatedOn,
                CreatedBy
            FROM District
            WHERE Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [district_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.error(f"DistrictHelper : get_district_by_id : {str(e)}")
        raise e

def check_district_name(name):
    """Check if district name exists"""
    logger.info(f"DistrictHelper : CheckDistrictName : Started")
    
    try:
        sql = "SELECT Name FROM District WHERE Name = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [name])
            row = cursor.fetchone()
            return row[0] if row else None
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
        with connection.cursor() as cursor:
            # Get class count
            class_sql = """
                SELECT COUNT(*) 
                FROM Class 
                WHERE CenterId = %s 
                AND DATE(StartedDate) >= %s 
                AND DATE(EndDate) <= %s
            """
            cursor.execute(class_sql, [center_id, start_date.date(), end_date.date()])
            class_count = cursor.fetchone()[0] or 0
            
            # Get holiday count
            holiday_sql = """
                SELECT COUNT(*) 
                FROM Holidays 
                WHERE CenterId = %s 
                AND DATE(StartDate) >= %s 
                AND DATE(EndDate) >= %s
            """
            cursor.execute(holiday_sql, [center_id, start_date.date(), end_date.date()])
            holiday_count = cursor.fetchone()[0] or 0
            
            # Get class cancel by teacher count
            cancel_sql = """
                SELECT COUNT(*) 
                FROM ClassCancelByTeacher 
                WHERE CenterId = %s 
                AND DATE(StartingDate) >= %s 
                AND DATE(EndingDate) >= %s
            """
            cursor.execute(cancel_sql, [center_id, start_date.date(), end_date.date()])
            cancel_count = cursor.fetchone()[0] or 0
            
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
            
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetClassCountByMonth : {str(e)}")
        raise e

def get_total_gender_ratio_by_center_id(center_id, start_date, end_date):
    """Get total gender ratio by center ID"""
    logger.info(f"DashboardHelper : GetTotalGenderRatioByCenterId : Started")
    
    try:
        with connection.cursor() as cursor:
            # Get total students
            total_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s 
                AND DATE(CreatedOn) >= %s 
                AND DATE(CreatedOn) <= %s
            """
            cursor.execute(total_sql, [center_id, start_date.date(), end_date.date()])
            total_students = cursor.fetchone()[0] or 0
            
            # Get female students
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
            
            # Get male students
            male_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s 
                AND Gender = 'Male'
                AND DATE(CreatedOn) >= %s 
                AND DATE(CreatedOn) <= %s
            """
            cursor.execute(male_sql, [center_id, start_date.date(), end_date.date()])
            male_count = cursor.fetchone()[0] or 0
            
            result = {
                "status": True,
                "data": [
                    {
                        "feMaleCount": female_count,
                        "maleCount": male_count,
                        "totalStudentCount": total_students
                    }
                ]
            }
            
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
                "status": True,
                "totalStudents": total_students,
                "data": []
            }
            
            grade_list = []
            for row in rows:
                grade = row[0]
                grade_list.append(grade)
                result["data"].append({
                    "grade": grade,
                    "feMaleCount": row[2] or 0,
                    "maleCount": row[3] or 0,
                    "totalStudentCount": row[1] or 0
                })
            
            # If no data, add all grades with 0
            if len(rows) == 0:
                for grade in list_of_existing_grade:
                    result["data"].append({
                        "grade": grade,
                        "feMaleCount": 0,
                        "maleCount": 0,
                        "totalStudentCount": 0
                    })
            else:
                # Add missing grades with 0
                list_not_in_db = [g for g in list_of_existing_grade if g not in grade_list]
                for grade in list_not_in_db:
                    result["data"].append({
                        "grade": grade,
                        "feMaleCount": 0,
                        "maleCount": 0,
                        "totalStudentCount": 0
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
        with connection.cursor() as cursor:
            # Get total BPL students
            bpl_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s 
                AND Bpl = 1
                AND DATE(CreatedOn) >= %s 
                AND DATE(CreatedOn) <= %s
            """
            cursor.execute(bpl_sql, [center_id, start_date.date(), end_date.date()])
            bpl_count = cursor.fetchone()[0] or 0
            
            # Get female BPL students
            female_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s 
                AND Bpl = 1
                AND Gender = 'FeMale'
                AND DATE(CreatedOn) >= %s 
                AND DATE(CreatedOn) <= %s
            """
            cursor.execute(female_sql, [center_id, start_date.date(), end_date.date()])
            female_count = cursor.fetchone()[0] or 0
            
            # Get male BPL students
            male_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s 
                AND Bpl = 1
                AND Gender = 'Male'
                AND DATE(CreatedOn) >= %s 
                AND DATE(CreatedOn) <= %s
            """
            cursor.execute(male_sql, [center_id, start_date.date(), end_date.date()])
            male_count = cursor.fetchone()[0] or 0
            
            # Get total students
            total_sql = """
                SELECT COUNT(*) 
                FROM Student 
                WHERE CenterId = %s
            """
            cursor.execute(total_sql, [center_id])
            total_students = cursor.fetchone()[0] or 0
            
            result = {
                "status": True,
                "totalStudents": total_students,
                "data": [
                    {
                        "feMaleCount": female_count,
                        "maleCount": male_count,
                        "totalBplStudents": bpl_count
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
                "status": True,
                "totalStudents": total_students,
                "data": []
            }
            
            for category in categories:
                result["data"].append({
                    "category": category,
                    "totalStudentCount": category_dict.get(category, 0)
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
    logger.info(f"DashboardHelper : GetTotalBplByFilter : Started")
    
    try:
        with connection.cursor() as cursor:
            # Build WHERE clause
            where_conditions = [
                "DATE(CreatedOn) >= %s",
                "DATE(CreatedOn) <= %s",
                "Bpl = 1",
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
            
            # Get total BPL students
            bpl_sql = f"""
                SELECT COUNT(*) 
                FROM Student 
                WHERE {where_clause}
            """
            cursor.execute(bpl_sql, params)
            bpl_count = cursor.fetchone()[0] or 0
            
            # Get female BPL students
            female_params = params.copy()
            female_sql = f"""
                SELECT COUNT(*) 
                FROM Student 
                WHERE {where_clause} AND Gender = 'FeMale'
            """
            cursor.execute(female_sql, female_params)
            female_count = cursor.fetchone()[0] or 0
            
            # Get male BPL students
            male_sql = f"""
                SELECT COUNT(*) 
                FROM Student 
                WHERE {where_clause} AND Gender = 'Male'
            """
            cursor.execute(male_sql, params)
            male_count = cursor.fetchone()[0] or 0
            
            # Get total students
            total_where = where_clause.replace("Bpl = 1 AND ", "")
            total_sql = f"""
                SELECT COUNT(*) 
                FROM Student 
                WHERE {total_where}
            """
            cursor.execute(total_sql, params[:3] + params[4:])
            total_students = cursor.fetchone()[0] or 0
            
            result = {
                "status": True,
                "totalStudents": total_students,
                "data": [
                    {
                        "feMaleCount": female_count,
                        "maleCount": male_count,
                        "totalBplStudents": bpl_count
                    }
                ]
            }
            
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalBplByFilter : {str(e)}")
        raise e

def get_total_gender_ratio_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get total gender ratio by filter"""
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
            
            # Get total students
            total_sql = f"""
                SELECT COUNT(*) 
                FROM Student 
                WHERE {where_clause}
            """
            cursor.execute(total_sql, params)
            total_students = cursor.fetchone()[0] or 0
            
            # Get female students
            female_sql = f"""
                SELECT COUNT(*) 
                FROM Student 
                WHERE {where_clause} AND Gender = 'FeMale'
            """
            cursor.execute(female_sql, params)
            female_count = cursor.fetchone()[0] or 0
            
            # Get male students
            male_sql = f"""
                SELECT COUNT(*) 
                FROM Student 
                WHERE {where_clause} AND Gender = 'Male'
            """
            cursor.execute(male_sql, params)
            male_count = cursor.fetchone()[0] or 0
            
            result = {
                "status": True,
                "data": [
                    {
                        "feMaleCount": female_count,
                        "maleCount": male_count,
                        "totalStudentCount": total_students
                    }
                ]
            }
            
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"DashboardHelper : GetTotalGenderRatioByFilter : {str(e)}")
        raise e

def get_total_student_category_of_class_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get total student category of class by filter"""
    logger.info(f"DashboardHelper : GetTotalStudentCategoryOfClassByFilter : Started")
    
    categories = ["General", "OBC", "SC", "ST", "EWS", "Others"]
    
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
            
            # Get students grouped by category
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
            
            # Create dict for quick lookup
            category_dict = {}
            for row in rows:
                category_dict[row[0]] = row[1]
            
            result = {
                "status": True,
                "data": []
            }
            
            for category in categories:
                result["data"].append({
                    "category": category,
                    "totalStudentCount": category_dict.get(category, 0)
                })
            
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
            "data": [
                {
                    "tenPercentage": 10,
                    "twentyPercentage": 20,
                    "thrityPercentage": 30,
                    "fourtyPercentage": 40,
                    "fiftyPercentage": 50,
                    "sixtyPercentage": 60,
                    "seventyPercentage": 70,
                    "eightyPercentage": 80,
                    "nintyPercentage": 90,
                    "hunderedPercentage": 100
                }
            ],
            "totalStudent": 100
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
        
        with connection.cursor() as cursor:
            if holiday_id > 0:
                # Get existing holidays with same name
                existing_sql = """
                    SELECT Id, CenterId, StartDate, EndDate, Name, Status, CreatedBy
                    FROM Holidays
                    WHERE Name = %s
                """
                cursor.execute(existing_sql, [name])
                existing_rows = cursor.fetchall()
                
                existing_center_ids = [row[1] for row in existing_rows]
                
                # Remove holidays that are not in the new list
                center_ids_to_remove = [cid for cid in existing_center_ids if cid not in center_ids]
                if center_ids_to_remove:
                    placeholders = ','.join(['%s'] * len(center_ids_to_remove))
                    remove_sql = f"""
                        DELETE FROM Holidays 
                        WHERE Name = %s AND CenterId IN ({placeholders})
                    """
                    params = [name] + center_ids_to_remove
                    cursor.execute(remove_sql, params)
                
                # Add new holidays
                center_ids_to_add = [cid for cid in center_ids if cid not in existing_center_ids]
                for center_id in center_ids_to_add:
                    insert_sql = """
                        INSERT INTO Holidays (
                            StartDate, EndDate, Name, Description, Status, CenterId, CreatedOn, CreatedBy
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, [
                        start_date,
                        end_date,
                        name,
                        description,
                        status,
                        center_id,
                        created_on,
                        created_by
                    ])
                
                # Update existing holidays
                for center_id in existing_center_ids:
                    if center_id in center_ids:
                        update_sql = """
                            UPDATE Holidays 
                            SET StartDate = %s, EndDate = %s, Name = %s, Description = %s, Status = %s
                            WHERE Name = %s AND CenterId = %s
                        """
                        cursor.execute(update_sql, [
                            start_date,
                            end_date,
                            name,
                            description,
                            status,
                            name,
                            center_id
                        ])
                        
            else:
                # Insert new holidays
                for center_id in center_ids:
                    insert_sql = """
                        INSERT INTO Holidays (
                            StartDate, EndDate, Name, Description, Status, CenterId, CreatedOn, CreatedBy
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, [
                        start_date,
                        end_date,
                        name,
                        description,
                        status,
                        center_id,
                        created_on,
                        created_by
                    ])
        
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
        sql = """
            SELECT 
                h.Id,
                h.Name,
                h.CenterId,
                h.Description
            FROM Holidays h
            INNER JOIN Center c ON h.CenterId = c.Id
            WHERE c.AssignedTeachers = %s 
            AND DATE(h.StartDate) >= %s 
            AND DATE(h.EndDate) <= %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [teacher_id, today, today])
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
            return result
            
    except Exception as e:
        logger.error(f"HolidaysHelper : GetAllHolidaysByTeacherId : {str(e)}")
        raise e

def get_all_holidays_by_year(year):
    """Get all holidays by year"""
    logger.info(f"HolidaysHelper : GetAllHolidaysByYear : Started")
    
    try:
        sql = """
            SELECT 
                Id, Name, Description, Status, StartDate, EndDate, CenterId, CreatedOn, CreatedBy
            FROM Holidays
            WHERE YEAR(StartDate) = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [year])
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
            return result
            
    except Exception as e:
        logger.error(f"HolidaysHelper : GetAllHolidaysByYear : {str(e)}")
        raise e

def get_all_holidays_by_center_id(center_id):
    """Get all holidays by center ID"""
    logger.info(f"HolidaysHelper : GetAllHolidaysByCenterId : Started")
    
    try:
        sql = """
            SELECT 
                Id, Name, Description, Status, StartDate, EndDate, CenterId, CreatedOn, CreatedBy
            FROM Holidays
            WHERE CenterId = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [center_id])
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
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
        
        with connection.cursor() as cursor:
            if user_id == 0:
                # SuperAdmin - get all holidays
                if status == 1:
                    # All holidays
                    sql = """
                        SELECT 
                            h.Id,
                            h.Name,
                            h.StartDate,
                            h.EndDate,
                            h.CreatedBy,
                            h.CreatedOn,
                            h.CenterId,
                            c.CenterName
                        FROM Holidays h
                        INNER JOIN Center c ON h.CenterId = c.Id
                        ORDER BY h.StartDate
                    """
                    cursor.execute(sql)
                else:
                    # Upcoming holidays
                    sql = """
                        SELECT 
                            h.Id,
                            h.Name,
                            h.StartDate,
                            h.EndDate,
                            h.CreatedBy,
                            h.CreatedOn,
                            h.CenterId,
                            c.CenterName
                        FROM Holidays h
                        INNER JOIN Center c ON h.CenterId = c.Id
                        WHERE DATE(h.StartDate) >= %s
                        ORDER BY h.StartDate
                    """
                    cursor.execute(sql, [today])
            else:
                # Regional Admin - filter by created_by
                if status == 1:
                    # All holidays
                    sql = """
                        SELECT 
                            h.Id,
                            h.Name,
                            h.StartDate,
                            h.EndDate,
                            h.CreatedBy,
                            h.CreatedOn,
                            h.CenterId,
                            c.CenterName
                        FROM Holidays h
                        INNER JOIN Center c ON h.CenterId = c.Id
                        WHERE h.CreatedBy = %s
                        ORDER BY h.StartDate
                    """
                    cursor.execute(sql, [user_id])
                else:
                    # Upcoming holidays
                    sql = """
                        SELECT 
                            h.Id,
                            h.Name,
                            h.StartDate,
                            h.EndDate,
                            h.CreatedBy,
                            h.CreatedOn,
                            h.CenterId,
                            c.CenterName
                        FROM Holidays h
                        INNER JOIN Center c ON h.CenterId = c.Id
                        WHERE h.CreatedBy = %s 
                        AND DATE(h.StartDate) >= %s
                        ORDER BY h.StartDate
                    """
                    cursor.execute(sql, [user_id, today])
            
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            for row in rows:
                result.append(dict(zip(columns, row)))
            
            return result
            
    except Exception as e:
        logger.error(f"HolidaysHelper : GetAllHolidays : {str(e)}")
        raise e

def delete_holiday_by_id(holiday_id):
    """Delete holiday by ID"""
    logger.info(f"HolidaysHelper : DeleteHolidayById : Started")
    
    try:
        with connection.cursor() as cursor:
            # Check if holiday exists
            check_sql = "SELECT Id FROM Holidays WHERE Id = %s"
            cursor.execute(check_sql, [holiday_id])
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Delete holiday
            delete_sql = "DELETE FROM Holidays WHERE Id = %s"
            cursor.execute(delete_sql, [holiday_id])
            
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
        with connection.cursor() as cursor:
            if offset == 0 and limit == 0:
                sql = """
                    SELECT 
                        p.Id,
                        p.PanchayatGuidId,
                        p.Name,
                        p.DistrictId,
                        d.Name as DistrictName,
                        p.VidhanSabhaId,
                        v.Name as VidhanSabhaName,
                        p.CreatedOn,
                        p.CreatedBy,
                        p.Status
                    FROM Panchayat p
                    INNER JOIN VidhanSabha v ON p.VidhanSabhaId = v.Id
                    INNER JOIN District d ON p.DistrictId = d.Id
                    ORDER BY p.Id
                """
                cursor.execute(sql)
            else:
                sql = """
                    SELECT 
                        p.Id,
                        p.PanchayatGuidId,
                        p.Name,
                        p.DistrictId,
                        d.Name as DistrictName,
                        p.VidhanSabhaId,
                        v.Name as VidhanSabhaName,
                        p.CreatedOn,
                        p.CreatedBy,
                        p.Status
                    FROM Panchayat p
                    INNER JOIN VidhanSabha v ON p.VidhanSabhaId = v.Id
                    INNER JOIN District d ON p.DistrictId = d.Id
                    ORDER BY p.Id
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, [limit, offset])
            
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
            return result
            
    except Exception as e:
        logger.error(f"PanchayatHelper : GetAllPanchayat : {str(e)}")
        raise e

def save_panchayat(panchayat_data):
    """Save or update panchayat"""
    logger.info(f"PanchayatHelper : SavePanchayat : Started")
    
    try:
        panchayat_id = panchayat_data.get('Id', 0)
        
        if panchayat_id > 0:
            # Update existing panchayat
            update_fields = []
            update_values = []
            
            for key, value in panchayat_data.items():
                if key != 'Id' and value is not None:
                    column_name = {
                        'Name': 'Name',
                        'Status': 'Status',
                        'CreatedBy': 'CreatedBy',
                        'PanchayatGuidId': 'PanchayatGuidId',
                        'DistrictId': 'DistrictId',
                        'VidhanSabhaId': 'VidhanSabhaId'
                    }.get(key, key)
                    
                    update_fields.append(f"{column_name} = %s")
                    update_values.append(value)
            
            if update_fields:
                update_values.append(panchayat_id)
                sql = f"""
                    UPDATE Panchayat 
                    SET {', '.join(update_fields)}
                    WHERE Id = %s
                """
                with connection.cursor() as cursor:
                    cursor.execute(sql, update_values)
        else:
            # Insert new panchayat
            panchayat_guid = str(uuid.uuid4())
            created_on = datetime.now()
            
            sql = """
                INSERT INTO Panchayat (
                    PanchayatGuidId, Name, Status, CreatedOn, CreatedBy, 
                    DistrictId, VidhanSabhaId
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [
                    panchayat_guid,
                    panchayat_data.get('Name'),
                    panchayat_data.get('Status'),
                    created_on,
                    panchayat_data.get('CreatedBy'),
                    panchayat_data.get('DistrictId'),
                    panchayat_data.get('VidhanSabhaId')
                ])
                
                cursor.execute("SELECT LAST_INSERT_ID()")
                panchayat_id = cursor.fetchone()[0]
        
        # Get the saved panchayat
        return get_panchayat_by_id(panchayat_id)
        
    except Exception as e:
        logger.error(f"PanchayatHelper : SavePanchayat : {str(e)}")
        raise e

def get_panchayat_by_id(panchayat_id):
    """Get panchayat by ID"""
    try:
        sql = """
            SELECT 
                p.Id,
                p.PanchayatGuidId,
                p.Name,
                p.DistrictId,
                d.Name as DistrictName,
                p.VidhanSabhaId,
                v.Name as VidhanSabhaName,
                p.CreatedOn,
                p.CreatedBy,
                p.Status
            FROM Panchayat p
            INNER JOIN VidhanSabha v ON p.VidhanSabhaId = v.Id
            INNER JOIN District d ON p.DistrictId = d.Id
            WHERE p.Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [panchayat_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.error(f"PanchayatHelper : get_panchayat_by_id : {str(e)}")
        raise e

def get_panchayat_by_district_and_vidhan_sabha_id(district_id, vidhan_sabha_id):
    """Get panchayat by district and vidhan sabha ID"""
    logger.info(f"PanchayatHelper : GetPanchayatByDistrictAndVidhanSabhaId : Started")
    
    try:
        sql = """
            SELECT 
                Id,
                PanchayatGuidId,
                Name,
                DistrictId,
                VidhanSabhaId,
                CreatedOn,
                CreatedBy,
                Status
            FROM Panchayat
            WHERE DistrictId = %s AND VidhanSabhaId = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [district_id, vidhan_sabha_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
        
    except Exception as e:
        logger.error(f"PanchayatHelper : GetPanchayatByDistrictAndVidhanSabhaId : {str(e)}")
        raise e

def check_panchayat_name(name):
    """Check if panchayat name exists"""
    logger.info(f"PanchayatHelper : CheckPanchayatName : Started")
    
    try:
        sql = "SELECT Name FROM Panchayat WHERE Name = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [name])
            row = cursor.fetchone()
            return row[0] if row else None
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
        
        with connection.cursor() as cursor:
            if student_id > 0:
                # Get existing student
                select_sql = "SELECT Status, LastClass, ActiveClassStatus, Counter FROM Student WHERE Id = %s"
                cursor.execute(select_sql, [student_id])
                existing = cursor.fetchone()
                
                if existing:
                    update_fields = []
                    update_values = []
                    
                    for key, value in student_data.items():
                        if key != 'Id' and value is not None:
                            column_name = {
                                'EnrollmentId': 'EnrollmentId',
                                'FullName': 'FullName',
                                'MotherName': 'MotherName',
                                'FatherName': 'FatherName',
                                'Age': 'Age',
                                'Gender': 'Gender',
                                'Contact': 'Contact',
                                'DateOfBirth': 'DateOfBirth',
                                'Email': 'Email',
                                'Remarks': 'Remarks',
                                'Grade': 'Grade',
                                'PhoneNumber': 'PhoneNumber',
                                'ProfileImage': 'ProfileImage',
                                'WhatsApp': 'WhatsApp',
                                'FullAddress': 'FullAddress',
                                'JoiningDate': 'JoiningDate',
                                'VidhanSabhaId': 'VidhanSabhaId',
                                'DistrictId': 'DistrictId',
                                'PanchayatId': 'PanchayatId',
                                'CenterId': 'CenterId',
                                'CreatedBy': 'CreatedBy',
                                'VillageId': 'VillageId',
                                'Education': 'Education',
                                'FatherMobileNumber': 'FatherMobileNumber',
                                'FatherOccupation': 'FatherOccupation',
                                'MotherMobileNumber': 'MotherMobileNumber',
                                'MotherOccupation': 'MotherOccupation',
                                'Category': 'Category',
                                'Bpl': 'Bpl',
                                'SchoolId': 'SchoolId',
                                'SchoolName': 'SchoolName'
                            }.get(key, key)
                            
                            update_fields.append(f"{column_name} = %s")
                            update_values.append(value)
                    
                    # Keep existing values for certain fields
                    update_fields.append("Status = %s")
                    update_values.append(existing[0])
                    
                    update_fields.append("LastClass = %s")
                    update_values.append(existing[1])
                    
                    update_fields.append("ActiveClassStatus = %s")
                    update_values.append(existing[2])
                    
                    update_fields.append("Counter = %s")
                    update_values.append(existing[3])
                    
                    update_fields.append("CreatedOn = %s")
                    update_values.append(datetime.now())
                    
                    update_fields.append("ManualAttendance = %s")
                    update_values.append(0)
                    
                    update_values.append(student_id)
                    sql = f"UPDATE Student SET {', '.join(update_fields)} WHERE Id = %s"
                    cursor.execute(sql, update_values)
            else:
                # Insert new student
                enrollment_id = student_data.get('EnrollmentId') or str(uuid.uuid4())
                created_on = datetime.now()
                
                columns = ['EnrollmentId', 'Status', 'CreatedOn', 'ActiveClassStatus', 'ManualAttendance']
                values = [enrollment_id, 1, created_on, 0, 0]
                
                field_mapping = {
                    'FullName': 'FullName',
                    'MotherName': 'MotherName',
                    'FatherName': 'FatherName',
                    'Age': 'Age',
                    'Gender': 'Gender',
                    'Contact': 'Contact',
                    'DateOfBirth': 'DateOfBirth',
                    'Email': 'Email',
                    'Remarks': 'Remarks',
                    'Grade': 'Grade',
                    'PhoneNumber': 'PhoneNumber',
                    'ProfileImage': 'ProfileImage',
                    'WhatsApp': 'WhatsApp',
                    'FullAddress': 'FullAddress',
                    'JoiningDate': 'JoiningDate',
                    'VidhanSabhaId': 'VidhanSabhaId',
                    'DistrictId': 'DistrictId',
                    'PanchayatId': 'PanchayatId',
                    'CenterId': 'CenterId',
                    'CreatedBy': 'CreatedBy',
                    'VillageId': 'VillageId',
                    'Education': 'Education',
                    'FatherMobileNumber': 'FatherMobileNumber',
                    'FatherOccupation': 'FatherOccupation',
                    'MotherMobileNumber': 'MotherMobileNumber',
                    'MotherOccupation': 'MotherOccupation',
                    'Category': 'Category',
                    'Bpl': 'Bpl',
                    'SchoolId': 'SchoolId',
                    'SchoolName': 'SchoolName'
                }
                
                for key, column in field_mapping.items():
                    if key in student_data and student_data[key] is not None:
                        columns.append(column)
                        values.append(student_data[key])
                
                placeholders = ', '.join(['%s'] * len(columns))
                sql = f"INSERT INTO Student ({', '.join(columns)}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                
                cursor.execute("SELECT LAST_INSERT_ID()")
                student_id = cursor.fetchone()[0]
        
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

def update_student_active_or_inactive(student_id, status):
    """Update student active or inactive status"""
    logger.info(f"StudentHelper : UpdateStudentActiveOrInactive : Started")
    
    try:
        status_bool = True if status == 1 else False
        
        sql = "UPDATE Student SET Status = %s WHERE Id = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [status_bool, student_id])
        
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
            user_type = user.type
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
            center_ids = list(Center.objects.values_list('id', flat=True))
        else:  # Regional Admin (Type 2)
            center_ids = list(Center.objects.filter(
                assigned_regional_admin=user_id
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
    """Save or update school"""
    logger.info(f"SchoolHelper : SaveSchool : Started")
    
    try:
        school_id = school_data.get('Id', 0)
        
        if school_id > 0:
            sql = "UPDATE School SET SchoolName = %s WHERE Id = %s"
            with connection.cursor() as cursor:
                cursor.execute(sql, [school_data.get('SchoolName'), school_id])
        else:
            created_on = datetime.now()
            sql = """
                INSERT INTO School (SchoolName, CreatedOn, CreatedBy)
                VALUES (%s, %s, %s)
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [
                    school_data.get('SchoolName'),
                    created_on,
                    school_data.get('CreatedBy')
                ])
                cursor.execute("SELECT LAST_INSERT_ID()")
                school_id = cursor.fetchone()[0]
        
        return get_school_by_id(school_id)
        
    except Exception as e:
        logger.error(f"SchoolHelper : SaveSchool : {str(e)}")
        raise e

def get_school_by_id(school_id):
    """Get school by ID"""
    try:
        sql = "SELECT Id, SchoolName, CreatedOn, CreatedBy FROM School WHERE Id = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [school_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.error(f"SchoolHelper : get_school_by_id : {str(e)}")
        raise e

def get_all_schools():
    """Get all schools"""
    logger.info(f"SchoolHelper : GetAllSchools : Started")
    
    try:
        sql = "SELECT Id, SchoolName, CreatedOn, CreatedBy FROM School ORDER BY Id"
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
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
            center_id=center_id
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
        
        sql = """
            SELECT 
                Id, TeacherGuidId, FullName, Age, Gender, DateOfBirth,
                PhoneNumber, WhatsApp, Email, Status, Count, Picture,
                Password, FullAddress, Education, Token,
                VidhanSabhaId, DistrictId, PanchayatId, CenterId, VillageId,
                CreatedOn, CreatedBy
            FROM Teacher
            WHERE FullName = %s AND Password = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [name, hashed_password])
            row = cursor.fetchone()
            
            if row:
                columns = [col[0] for col in cursor.description]
                teacher_dict = dict(zip(columns, row))
                
                # Generate token
                token = AccessToken()
                token['teacher_id'] = teacher_dict.get('Id')
                token['teacher_name'] = teacher_dict.get('FullName')
                token.set_exp(lifetime=timedelta(days=30))
                teacher_dict['Token'] = str(token)
                
                return teacher_dict
        
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
    """Get teacher by ID"""
    try:
        sql = """
            SELECT 
                Id, TeacherGuidId, FullName, Age, Gender, DateOfBirth,
                PhoneNumber, WhatsApp, Email, Status, Count, Picture,
                Password, FullAddress, Education, Token,
                VidhanSabhaId, DistrictId, PanchayatId, CenterId, VillageId,
                CreatedOn, CreatedBy
            FROM Teacher
            WHERE Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [teacher_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
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
        with connection.cursor() as cursor:
            if offset == 0 and limit == 0:
                sql = """
                    SELECT 
                        v.Id,
                        v.VidhanSabhaGuidId,
                        v.Name,
                        v.DistrictId,
                        d.Name as DistrictName,
                        v.CreatedOn,
                        v.CreatedBy,
                        v.Status
                    FROM VidhanSabha v
                    INNER JOIN District d ON v.DistrictId = d.Id
                    ORDER BY v.Id
                """
                cursor.execute(sql)
            else:
                sql = """
                    SELECT 
                        v.Id,
                        v.VidhanSabhaGuidId,
                        v.Name,
                        v.DistrictId,
                        d.Name as DistrictName,
                        v.CreatedOn,
                        v.CreatedBy,
                        v.Status
                    FROM VidhanSabha v
                    INNER JOIN District d ON v.DistrictId = d.Id
                    ORDER BY v.Id
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, [limit, offset])
            
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
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
            update_fields = []
            update_values = []
            
            for key, value in vidhan_sabha_data.items():
                if key != 'Id' and value is not None:
                    column_name = {
                        'Name': 'Name',
                        'Status': 'Status',
                        'CreatedBy': 'CreatedBy',
                        'VidhanSabhaGuidId': 'VidhanSabhaGuidId',
                        'DistrictId': 'DistrictId'
                    }.get(key, key)
                    
                    update_fields.append(f"{column_name} = %s")
                    update_values.append(value)
            
            if update_fields:
                update_values.append(vidhan_sabha_id)
                sql = f"UPDATE VidhanSabha SET {', '.join(update_fields)} WHERE Id = %s"
                with connection.cursor() as cursor:
                    cursor.execute(sql, update_values)
        else:
            vidhan_sabha_guid = str(uuid.uuid4())
            created_on = datetime.now()
            
            sql = """
                INSERT INTO VidhanSabha (
                    VidhanSabhaGuidId, Name, Status, CreatedOn, CreatedBy, DistrictId
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [
                    vidhan_sabha_guid,
                    vidhan_sabha_data.get('Name'),
                    vidhan_sabha_data.get('Status'),
                    created_on,
                    vidhan_sabha_data.get('CreatedBy'),
                    vidhan_sabha_data.get('DistrictId')
                ])
                cursor.execute("SELECT LAST_INSERT_ID()")
                vidhan_sabha_id = cursor.fetchone()[0]
        
        return get_vidhan_sabha_by_id(vidhan_sabha_id)
        
    except Exception as e:
        logger.error(f"VidhanSabhaHelper : SaveVidhanSabha : {str(e)}")
        raise e

def get_vidhan_sabha_by_id(vidhan_sabha_id):
    """Get VidhanSabha by ID"""
    try:
        sql = """
            SELECT 
                v.Id,
                v.VidhanSabhaGuidId,
                v.Name,
                v.DistrictId,
                d.Name as DistrictName,
                v.CreatedOn,
                v.CreatedBy,
                v.Status
            FROM VidhanSabha v
            INNER JOIN District d ON v.DistrictId = d.Id
            WHERE v.Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [vidhan_sabha_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.error(f"VidhanSabhaHelper : get_vidhan_sabha_by_id : {str(e)}")
        raise e

def get_vidhan_sabha_by_district_id(district_id):
    """Get VidhanSabha by district ID"""
    logger.info(f"VidhanSabhaHelper : GetVidhanSabhaByDistrictId : Started")
    
    try:
        sql = """
            SELECT 
                Id, VidhanSabhaGuidId, Name, DistrictId, CreatedOn, CreatedBy, Status
            FROM VidhanSabha
            WHERE DistrictId = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [district_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
        
    except Exception as e:
        logger.error(f"VidhanSabhaHelper : GetVidhanSabhaByDistrictId : {str(e)}")
        raise e

def check_vidhan_sabha_name(name):
    """Check if VidhanSabha name exists"""
    logger.info(f"VidhanSabhaHelper : CheckVidhanSabhaName : Started")
    
    try:
        sql = "SELECT Name FROM VidhanSabha WHERE Name = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [name])
            row = cursor.fetchone()
            return row[0] if row else None
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
        with connection.cursor() as cursor:
            if offset == 0 and limit == 0:
                sql = """
                    SELECT 
                        v.Id,
                        v.VillageGuidId,
                        v.Name,
                        v.DistrictId,
                        d.Name as DistrictName,
                        v.VidhanSabhaId,
                        vid.Name as VidhanSabhaName,
                        v.PanchayatId,
                        p.Name as PanchayatName,
                        v.CreatedOn,
                        v.CreatedBy,
                        v.Status
                    FROM Village v
                    INNER JOIN Panchayat p ON v.PanchayatId = p.Id
                    INNER JOIN District d ON v.DistrictId = d.Id
                    INNER JOIN VidhanSabha vid ON v.VidhanSabhaId = vid.Id
                    ORDER BY v.Id
                """
                cursor.execute(sql)
            else:
                sql = """
                    SELECT 
                        v.Id,
                        v.VillageGuidId,
                        v.Name,
                        v.DistrictId,
                        d.Name as DistrictName,
                        v.VidhanSabhaId,
                        vid.Name as VidhanSabhaName,
                        v.PanchayatId,
                        p.Name as PanchayatName,
                        v.CreatedOn,
                        v.CreatedBy,
                        v.Status
                    FROM Village v
                    INNER JOIN Panchayat p ON v.PanchayatId = p.Id
                    INNER JOIN District d ON v.DistrictId = d.Id
                    INNER JOIN VidhanSabha vid ON v.VidhanSabhaId = vid.Id
                    ORDER BY v.Id
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, [limit, offset])
            
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
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
            update_fields = []
            update_values = []
            
            for key, value in village_data.items():
                if key != 'Id' and value is not None:
                    column_name = {
                        'Name': 'Name',
                        'Status': 'Status',
                        'CreatedBy': 'CreatedBy',
                        'VillageGuidId': 'VillageGuidId',
                        'DistrictId': 'DistrictId',
                        'VidhanSabhaId': 'VidhanSabhaId',
                        'PanchayatId': 'PanchayatId'
                    }.get(key, key)
                    
                    update_fields.append(f"{column_name} = %s")
                    update_values.append(value)
            
            if update_fields:
                update_values.append(village_id)
                sql = f"UPDATE Village SET {', '.join(update_fields)} WHERE Id = %s"
                with connection.cursor() as cursor:
                    cursor.execute(sql, update_values)
        else:
            village_guid = str(uuid.uuid4())
            created_on = datetime.now()
            
            sql = """
                INSERT INTO Village (
                    VillageGuidId, Name, Status, CreatedOn, CreatedBy,
                    DistrictId, VidhanSabhaId, PanchayatId
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [
                    village_guid,
                    village_data.get('Name'),
                    village_data.get('Status'),
                    created_on,
                    village_data.get('CreatedBy'),
                    village_data.get('DistrictId'),
                    village_data.get('VidhanSabhaId'),
                    village_data.get('PanchayatId')
                ])
                cursor.execute("SELECT LAST_INSERT_ID()")
                village_id = cursor.fetchone()[0]
        
        return get_village_by_id(village_id)
        
    except Exception as e:
        logger.error(f"VillageHelper : SaveVillage : {str(e)}")
        raise e

def get_village_by_id(village_id):
    """Get village by ID"""
    try:
        sql = """
            SELECT 
                v.Id,
                v.VillageGuidId,
                v.Name,
                v.DistrictId,
                d.Name as DistrictName,
                v.VidhanSabhaId,
                vid.Name as VidhanSabhaName,
                v.PanchayatId,
                p.Name as PanchayatName,
                v.CreatedOn,
                v.CreatedBy,
                v.Status
            FROM Village v
            INNER JOIN Panchayat p ON v.PanchayatId = p.Id
            INNER JOIN District d ON v.DistrictId = d.Id
            INNER JOIN VidhanSabha vid ON v.VidhanSabhaId = vid.Id
            WHERE v.Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [village_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.error(f"VillageHelper : get_village_by_id : {str(e)}")
        raise e

def get_village_by_district_vidhan_sabha_and_panchayat(district_id, vidhan_sabha_id, panchayat_id):
    """Get village by district, vidhan sabha and panchayat IDs"""
    logger.info(f"VillageHelper : GetVillageByDistrictVidhanSabhaAndPanchId : Started")
    
    try:
        sql = """
            SELECT 
                Id, VillageGuidId, Name, DistrictId, VidhanSabhaId, PanchayatId,
                CreatedOn, CreatedBy, Status
            FROM Village
            WHERE DistrictId = %s AND VidhanSabhaId = %s AND PanchayatId = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [district_id, vidhan_sabha_id, panchayat_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
        
    except Exception as e:
        logger.error(f"VillageHelper : GetVillageByDistrictVidhanSabhaAndPanchId : {str(e)}")
        raise e

def check_village_name(name):
    """Check if village name exists"""
    logger.info(f"VillageHelper : CheckVillageName : Started")
    
    try:
        sql = "SELECT Name FROM Village WHERE Name = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [name])
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"VillageHelper : CheckVillageName : {str(e)}")
        raise e
    
#---------------------------------------------------------
# RegionalAdmin APIs Helper Functions
#---------------------------------------------------------

def get_all_regional_admins():
    """Get all regional admins"""
    logger.info(f"RegionalAdminHelper : GetAllRegionalAdmin : Started")
    
    try:
        sql = """
            SELECT 
                Id, RegionalAdminGuidId, FullName, Age, Gender, DateOfBirth,
                PhoneNumber, WhatsApp, Email, Contact, Status, RoleId,
                Picture, LastLoginTime, Password, FullAddress, Type, Token,
                VidhanSabhaId, DistrictId, PanchayatId, CenterId, VillageId,
                CreatedOn, CreatedBy
            FROM RegionalAdmin
            ORDER BY Id
        """
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
            return result
            
    except Exception as e:
        logger.error(f"RegionalAdminHelper : GetAllRegionalAdmin : {str(e)}")
        raise e

def login_regional_admin(name, password):
    """Login regional admin by name and password"""
    logger.info(f"RegionalAdminHelper : LoginRegionalAdmin : Started")
    
    try:
        hashed_password = hash_password(password)
        
        sql = """
            SELECT 
                Id, RegionalAdminGuidId, FullName, Age, Gender, DateOfBirth,
                PhoneNumber, WhatsApp, Email, Contact, Status, RoleId,
                Picture, LastLoginTime, Password, FullAddress, Type, Token,
                VidhanSabhaId, DistrictId, PanchayatId, CenterId, VillageId,
                CreatedOn, CreatedBy
            FROM RegionalAdmin
            WHERE FullName = %s AND Password = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [name, hashed_password])
            row = cursor.fetchone()
            
            if row:
                columns = [col[0] for col in cursor.description]
                regional_admin_dict = dict(zip(columns, row))
                
                # Generate token
                token = AccessToken()
                token['regional_admin_id'] = regional_admin_dict.get('Id')
                token['regional_admin_name'] = regional_admin_dict.get('FullName')
                token.set_exp(lifetime=timedelta(days=30))
                regional_admin_dict['Token'] = str(token)
                
                return regional_admin_dict
        
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
    """Get regional admin by ID"""
    try:
        sql = """
            SELECT 
                Id, RegionalAdminGuidId, FullName, Age, Gender, DateOfBirth,
                PhoneNumber, WhatsApp, Email, Contact, Status, RoleId,
                Picture, LastLoginTime, Password, FullAddress, Type, Token,
                VidhanSabhaId, DistrictId, PanchayatId, CenterId, VillageId,
                CreatedOn, CreatedBy
            FROM RegionalAdmin
            WHERE Id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [regional_admin_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
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
        sql = "SELECT Id, Title, Description, Image, CreatedOn, CreatedBy FROM Announcement WHERE Id = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [announcement_id])
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.error(f"AnnouncementHelper : get_announcement_by_id : {str(e)}")
        raise e

def get_all_announcements():
    """Get all announcements"""
    logger.info(f"AnnouncementHelper : GetAnnouncement : Started")
    
    try:
        sql = "SELECT Id, Title, Description, Image, CreatedOn, CreatedBy FROM Announcement ORDER BY Id"
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
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
    
    