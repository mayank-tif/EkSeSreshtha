import json
import logging
from datetime import datetime
from django.db.models import OuterRef, Subquery, Count
from .models import *
from django.db import connection
from .utils import *
from rest_framework_simplejwt.tokens import AccessToken
from datetime import timedelta


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
    logger.info(f"CenterRepository : GetCenteryId : Started")
    
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
        logger.error(f"CenterRepository : GetCenteryId : {str(e)}")
        raise e

def get_center_by_user_id(user_id):
    """Get center assigned to a teacher"""
    logger.info(f"CenterRepository : GetCenterByUserId : Started")
    
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
        logger.error(f"CenterRepository : GetCenterByUserId : {str(e)}")
        raise e

def get_all_center_attendance(user_id, date, offset, limit):
    """Get all center attendance"""
    logger.info(f"CenterRepository : GetAllCenterAttendance : Started")
    
    try:
        # Get user type
        user_type_sql = "SELECT Type FROM Users WHERE Id = %s"
        with connection.cursor() as cursor:
            cursor.execute(user_type_sql, [user_id])
            user_row = cursor.fetchone()
            user_type = user_row[0] if user_row else None
        
        centers = []
        
        if user_type == 1:
            sql = """
                SELECT 
                    c.Id,
                    c.CenterName,
                    c.AssignedTeachers,
                    c.AssignedRegionalAdmin,
                    cls.StartedDate as ClassStartedDate,
                    cls.EndDate as ClassEndDate,
                    cls.TotalStudents,
                    cls.AvilableStudents as PresentStudents,
                    u1.Name as TeacherName,
                    u2.Name as RegionalAdminName,
                    CASE WHEN cls.Id IS NOT NULL THEN 1 ELSE 2 END as Type
                FROM Center c
                LEFT JOIN Class cls ON c.Id = cls.CenterId AND DATE(cls.StartedDate) = %s
                LEFT JOIN Users u1 ON c.AssignedTeachers = u1.Id
                LEFT JOIN Users u2 ON c.AssignedRegionalAdmin = u2.Id
                ORDER BY c.Id
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql, [date, limit, offset])
        else:
            sql = """
                SELECT 
                    c.Id,
                    c.CenterName,
                    c.AssignedTeachers,
                    c.AssignedRegionalAdmin,
                    cls.StartedDate as ClassStartedDate,
                    cls.EndDate as ClassEndDate,
                    cls.TotalStudents,
                    cls.AvilableStudents as PresentStudents,
                    u1.Name as TeacherName,
                    u2.Name as RegionalAdminName,
                    CASE WHEN cls.Id IS NOT NULL THEN 1 ELSE 2 END as Type
                FROM Center c
                LEFT JOIN Class cls ON c.Id = cls.CenterId AND DATE(cls.StartedDate) = %s
                LEFT JOIN Users u1 ON c.AssignedTeachers = u1.Id
                LEFT JOIN Users u2 ON c.AssignedRegionalAdmin = u2.Id
                WHERE c.AssignedRegionalAdmin = %s
                ORDER BY c.Id
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql, [date, user_id, limit, offset])
        
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
        for row in rows:
            center_dict = dict(zip(columns, row))
            
            # Set null fields
            center_dict['StartDate'] = None
            center_dict['EndDate'] = None
            center_dict['Reason'] = None
            
            # If no class exists (Type == 2), check for holidays and cancellations
            if center_dict.get('Type') == 2:
                center_id = center_dict.get('Id')
                
                # Check holidays
                holiday_sql = """
                    SELECT StartDate, EndDate
                    FROM Holidays
                    WHERE CenterId = %s AND DATE(StartDate) <= %s AND DATE(EndDate) >= %s
                """
                cursor.execute(holiday_sql, [center_id, date, date])
                holiday_row = cursor.fetchone()
                
                if holiday_row:
                    center_dict['Type'] = 3
                    center_dict['Reason'] = 'Holiday'
                    center_dict['StartDate'] = holiday_row[0]
                    center_dict['EndDate'] = holiday_row[1]
                
                # Check class cancel by teacher
                cancel_sql = """
                    SELECT StartingDate, EndingDate
                    FROM ClassCancelByTeacher
                    WHERE CenterId = %s AND DATE(StartingDate) <= %s AND DATE(EndingDate) >= %s
                """
                cursor.execute(cancel_sql, [center_id, date, date])
                cancel_row = cursor.fetchone()
                
                if cancel_row:
                    center_dict['Type'] = 4
                    center_dict['Reason'] = 'Class cancel by teacher'
                    center_dict['StartDate'] = cancel_row[0]
                    center_dict['EndDate'] = cancel_row[1]
            
            centers.append(center_dict)
        
        logger.info(f"CenterRepository : GetAllCenterAttendance : End")
        return centers
        
    except Exception as e:
        logger.error(f"CenterRepository : GetAllCenterAttendance : {str(e)}")
        raise e

def get_total_attendance_count_of_center(user_id, date):
    """Get total attendance count of center"""
    logger.info(f"CenterRepository : GetTotalAttendanceCountOfCenter : Started")
    
    try:
        # Get user type
        user_type_sql = "SELECT Type FROM Users WHERE Id = %s"
        with connection.cursor() as cursor:
            cursor.execute(user_type_sql, [user_id])
            user_row = cursor.fetchone()
            user_type = user_row[0] if user_row else None
        
        if user_type == 1:
            sql = """
                SELECT 
                    COUNT(CASE WHEN cls.Id IS NULL THEN 1 END) as NotStarted,
                    COUNT(CASE WHEN cls.Id IS NOT NULL AND DATE(cls.StartedDate) = %s AND cls.AvilableStudents = 0 AND cls.EndDate IS NULL THEN 1 END) as EndDateWithNoAttendance,
                    COUNT(CASE WHEN cls.Id IS NOT NULL AND DATE(cls.StartedDate) = %s AND cls.AvilableStudents > 0 AND cls.EndDate IS NULL THEN 1 END) as EndDateWithAttendance,
                    COUNT(CASE WHEN cls.Id IS NOT NULL AND DATE(cls.StartedDate) = %s AND cls.AvilableStudents > 0 AND cls.EndDate IS NOT NULL THEN 1 END) as CompletedWithAttendance,
                    COUNT(CASE WHEN cls.Id IS NOT NULL AND DATE(cls.StartedDate) = %s AND cls.AvilableStudents = 0 AND cls.EndDate IS NOT NULL THEN 1 END) as NoAttendance
                FROM Center c
                LEFT JOIN Class cls ON c.Id = cls.CenterId
            """
            cursor.execute(sql, [date, date, date, date])
        else:
            sql = """
                SELECT 
                    COUNT(CASE WHEN cls.Id IS NULL THEN 1 END) as NotStarted,
                    COUNT(CASE WHEN cls.Id IS NOT NULL AND DATE(cls.StartedDate) = %s AND cls.AvilableStudents = 0 AND cls.EndDate IS NULL THEN 1 END) as EndDateWithNoAttendance,
                    COUNT(CASE WHEN cls.Id IS NOT NULL AND DATE(cls.StartedDate) = %s AND cls.AvilableStudents > 0 AND cls.EndDate IS NULL THEN 1 END) as EndDateWithAttendance,
                    COUNT(CASE WHEN cls.Id IS NOT NULL AND DATE(cls.StartedDate) = %s AND cls.AvilableStudents > 0 AND cls.EndDate IS NOT NULL THEN 1 END) as CompletedWithAttendance,
                    COUNT(CASE WHEN cls.Id IS NOT NULL AND DATE(cls.StartedDate) = %s AND cls.AvilableStudents = 0 AND cls.EndDate IS NOT NULL THEN 1 END) as NoAttendance
                FROM Center c
                LEFT JOIN Class cls ON c.Id = cls.CenterId
                WHERE c.AssignedRegionalAdmin = %s
            """
            cursor.execute(sql, [date, date, date, date, user_id])
        
        row = cursor.fetchone()
        
        result = {
            "NotStarted": row[0] or 0,
            "NoEndDateWithNoAttendance": row[1] or 0,
            "NoEndDateWithAttendance": row[2] or 0,
            "Completed": row[3] or 0,
            "NoAttendance": row[4] or 0,
            "Status": True
        }
        
        logger.info(f"CenterRepository : GetTotalAttendanceCountOfCenter : End")
        return result
        
    except Exception as e:
        logger.error(f"CenterRepository : GetTotalAttendanceCountOfCenter : {str(e)}")
        raise e

def update_center_active_or_deactive(center_log_data):
    """Update center active or deactive status"""
    logger.info(f"CenterRepository : UpdateCenterActiveOrDeactive : Started")
    
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
        
        logger.info(f"CenterRepository : UpdateCenterActiveOrDeactive : End")
        return {'centerId': center_id, 'status': status}
        
    except Exception as e:
        logger.error(f"CenterRepository : UpdateCenterActiveOrDeactive : {str(e)}")
        raise e


# TECHERS SECTION ----------------------------------------------------------
def get_all_teachers(userId):
    """Get all teachers with optional filtering by userId"""
    logger.info(f"UserRepository : GetRegisteredTeachers : Started")
    
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
        
        logger.info(f"UserRepository : GetRegisteredTeachers : End")
        return result
        
    except Exception as e:
        logger.error(f"UserRepository : GetRegisteredTeachers : {str(e)}")
        raise e
    


#---------------------------------------------------------
def get_all_regional_admins():
    """Get all regional admins (Type == RegionalAdmin)"""
    logger.info(f"UserRepository : GetAllRegionalAdmins : Started")
    
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
        
        logger.info(f"UserRepository : GetAllRegionalAdmins : End")
        return result
        
    except Exception as e:
        logger.error(f"UserRepository : GetAllRegionalAdmins : {str(e)}")
        raise e



# USER SECTION---------------------------------------------------------
def login_user(mobile_number, password):
    """Authenticate user by mobile number and password"""
    logger.info(f"UserRepository : LoginUser : Started")
    
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
                
                logger.info(f"UserRepository : LoginUser : End")
                return response_data
        
        return None
        
    except Exception as e:
        logger.error(f"UserRepository : LoginUser : {str(e)}")
        raise e
    
    
def save_user(user_data):
    """Save or update user"""
    logger.info(f"UserRepository : SaveLogin : Started")
    
    try:
        user_id = user_data.get('Id', 0)
        
        if user_id > 0:
            # Update existing user
            update_fields = []
            update_values = []
            
            # Build update query dynamically
            for key, value in user_data.items():
                if key != 'Id' and value is not None:
                    # Convert field names to column names
                    column_name = {
                        'enrolmentRollId': 'EnrolmentRollId',
                        'deviceId': 'DeviceId',
                        'dateOfBirth': 'DateOfBirth',
                        'phoneNumber': 'PhoneNumber',
                        'whatsApp': 'WhatsApp',
                        'lastLoginTime': 'LastLoginTime',
                        'fullAddress': 'FullAddress',
                        'roleId': 'RoleId',
                        'createdOn': 'CreatedOn',
                        'enrollmentDate': 'EnrollmentDate',
                        'createdBy': 'CreatedBy',
                        'vidhanSabhaId': 'VidhanSabhaId',
                        'districtId': 'DistrictId',
                        'villageId': 'VillageId',
                        'panchayatId': 'PanchayatId',
                        'assignedTeacherStatus': 'AssignedTeacherStatus',
                        'assignedRegionalAdminStatus': 'AssignedRegionalAdminStatus',
                        'guardianName': 'GuardianName',
                        'guardianNumber': 'GuardianNumber',
                        'fullName': 'FullName',
                        'assignedTeacher': 'AssignedTeacher',
                        'assignedRegionalAdmin': 'AssignedRegionalAdmin'
                    }.get(key, key)
                    
                    update_fields.append(f"{column_name} = %s")
                    update_values.append(value)
            
            if update_fields:
                update_values.append(user_id)
                sql = f"""
                    UPDATE Users 
                    SET {', '.join(update_fields)}
                    WHERE Id = %s
                """
                with connection.cursor() as cursor:
                    cursor.execute(sql, update_values)
        else:
            # Insert new user
            columns = []
            placeholders = []
            values = []
            
            for key, value in user_data.items():
                if key != 'Id' and value is not None:
                    column_name = {
                        'enrolmentRollId': 'EnrolmentRollId',
                        'deviceId': 'DeviceId',
                        'dateOfBirth': 'DateOfBirth',
                        'phoneNumber': 'PhoneNumber',
                        'whatsApp': 'WhatsApp',
                        'lastLoginTime': 'LastLoginTime',
                        'fullAddress': 'FullAddress',
                        'roleId': 'RoleId',
                        'createdOn': 'CreatedOn',
                        'enrollmentDate': 'EnrollmentDate',
                        'createdBy': 'CreatedBy',
                        'vidhanSabhaId': 'VidhanSabhaId',
                        'districtId': 'DistrictId',
                        'villageId': 'VillageId',
                        'panchayatId': 'PanchayatId',
                        'assignedTeacherStatus': 'AssignedTeacherStatus',
                        'assignedRegionalAdminStatus': 'AssignedRegionalAdminStatus',
                        'guardianName': 'GuardianName',
                        'guardianNumber': 'GuardianNumber'
                    }.get(key, key)
                    
                    columns.append(column_name)
                    placeholders.append('%s')
                    values.append(value)
            
            # Set default values
            columns.append('CreatedOn')
            placeholders.append('%s')
            values.append(datetime.now())
            
            columns.append('AssignedTeacherStatus')
            placeholders.append('%s')
            values.append(False)
            
            columns.append('AssignedRegionalAdminStatus')
            placeholders.append('%s')
            values.append(False)
            
            columns.append('Status')
            placeholders.append('%s')
            values.append(True)
            
            if user_data.get('Type') == 3:  # Teacher
                if user_data.get('ListOfPanchayatIds'):
                    panchayat_list = user_data.get('ListOfPanchayatIds')
                    if isinstance(panchayat_list, list) and len(panchayat_list) == 1:
                        columns.append('PanchayatId')
                        placeholders.append('%s')
                        values.append(int(panchayat_list[0]))
            
            sql = f"""
                INSERT INTO Users ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                
                # Get the inserted ID
                cursor.execute("SELECT LAST_INSERT_ID()")
                user_id = cursor.fetchone()[0]
        
        return get_user_by_id(user_id)
        
    except Exception as e:
        logger.error(f"UserRepository : SaveLogin : {str(e)}")
        raise e

def get_user_by_id(user_id):
    """Get user by ID"""
    logger.info(f"UserRepository : GetUserById : Started")
    
    try:
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
            WHERE u.Id = %s
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql, [user_id])
            row = cursor.fetchone()
            
            if row:
                columns = [col[0] for col in cursor.description]
                user_dict = dict(zip(columns, row))
                
                # Get additional data based on user type
                if user_dict.get('Type') == 3:  # Teacher
                    # Get center details
                    center_sql = """
                        SELECT c.*, 
                               d.Name as DistrictName,
                               v.Name as VidhanSabhaName,
                               p.Name as PanchayatName,
                               vi.Name as VillageName
                        FROM Center c
                        LEFT JOIN District d ON c.DistrictId = d.Id
                        LEFT JOIN VidhanSabha v ON c.VidhanSabhaId = v.Id
                        LEFT JOIN Panchayat p ON c.PanchayatId = p.Id
                        LEFT JOIN Village vi ON c.VillageId = vi.Id
                        WHERE c.AssignedTeachers = %s
                    """
                    cursor.execute(center_sql, [user_id])
                    center_row = cursor.fetchone()
                    if center_row:
                        center_columns = [col[0] for col in cursor.description]
                        user_dict['Center'] = dict(zip(center_columns, center_row))
                
                elif user_dict.get('Type') == 2:  # Regional Admin
                    # Get centers
                    centers_sql = """
                        SELECT c.* 
                        FROM Center c
                        WHERE c.AssignedRegionalAdmin = %s
                    """
                    cursor.execute(centers_sql, [user_id])
                    centers_rows = cursor.fetchall()
                    if centers_rows:
                        center_columns = [col[0] for col in cursor.description]
                        user_dict['Centers'] = [dict(zip(center_columns, row)) for row in centers_rows]
                    
                    # Get panchayats
                    panchayat_sql = """
                        SELECT rp.*, p.Name as PanchayatName
                        FROM RegionalAdminPanchayat rp
                        JOIN Panchayat p ON rp.PanchayatId = p.Id
                        WHERE rp.UsersId = %s
                    """
                    cursor.execute(panchayat_sql, [user_id])
                    panchayat_rows = cursor.fetchall()
                    if panchayat_rows:
                        panchayat_columns = [col[0] for col in cursor.description]
                        user_dict['RegionalAdminPanchayat'] = [dict(zip(panchayat_columns, row)) for row in panchayat_rows]
                
                return user_dict
        
        return None
        
    except Exception as e:
        logger.error(f"UserRepository : GetUserById : {str(e)}")
        raise e

def update_user_device_id(user_id, device_id):
    """Update user device ID"""
    logger.info(f"UserRepository : UpdateDeviceId : Started")
    
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
        logger.error(f"UserRepository : UpdateDeviceId : {str(e)}")
        raise e

def update_user_password(user_id, new_password):
    """Update user password"""
    logger.info(f"UserRepository : UpdatePassword : Started")
    
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
        logger.error(f"UserRepository : UpdatePassword : {str(e)}")
        raise e

def get_user_detail_by_phone(phone_number):
    """Get user details by phone number"""
    logger.info(f"UserRepository : GetUserDetailByPhoneNumber : Started")
    
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
        logger.error(f"UserRepository : GetUserDetailByPhoneNumber : {str(e)}")
        raise e

def search_data(search_type, query_string):
    """Search data by type and query string"""
    logger.info(f"UserRepository : SearchData : Started")
    
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
        
        logger.info(f"UserRepository : SearchData : End")
        return results
        
    except Exception as e:
        logger.error(f"UserRepository : SearchData : {str(e)}")
        raise e

#---------------------------------------------------------
# Class APIs Helper Functions
#---------------------------------------------------------

def save_class(class_data):
    """Save a new class"""
    logger.info(f"ClassRepository : SaveClass : Started")
    
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
        logger.error(f"ClassRepository : SaveClass : {str(e)}")
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
        logger.error(f"ClassRepository : get_class_by_id : {str(e)}")
        raise e

def cancel_class(class_data):
    """Cancel a class"""
    logger.info(f"ClassRepository : CancelClass : Started")
    
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
        logger.error(f"ClassRepository : CancelClass : {str(e)}")
        raise e

def update_end_class_time(class_id):
    """Update end class time"""
    logger.info(f"ClassRepository : UpdateEndClassTime : Started")
    
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
        logger.error(f"ClassRepository : UpdateEndClassTime : {str(e)}")
        raise e

def update_class_sub_status(class_id):
    """Update class sub status"""
    logger.info(f"ClassRepository : UpdateClassSubStatus : Started")
    
    try:
        sql = "UPDATE Class SET SubStatus = 1 WHERE Id = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [class_id])
        
        return get_class_by_id(class_id)
        
    except Exception as e:
        logger.error(f"ClassRepository : UpdateClassSubStatus : {str(e)}")
        raise e

def cancel_class_by_teacher(class_cancel_data):
    """Cancel class by teacher"""
    logger.info(f"ClassRepository : CancelClassByTeacher : Started")
    
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
        logger.error(f"ClassRepository : CancelClassByTeacher : {str(e)}")
        raise e

def delete_class_by_teacher_id(class_id):
    """Delete class by teacher ID"""
    logger.info(f"ClassRepository : DeleteClassByTeacherId : Started")
    
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
        logger.error(f"ClassRepository : DeleteClassByTeacherId : {str(e)}")
        raise e

def get_class_current_status(center_id, teacher_id):
    """Get class current status"""
    logger.info(f"ClassRepository : GetClassCurrentStatus : Started")
    
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
        logger.error(f"ClassRepository : GetClassCurrentStatus : {str(e)}")
        raise e

def get_live_class_detail(class_id):
    """Get live class detail"""
    logger.info(f"ClassRepository : GetLiveClassDetail : Started")
    
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
        logger.error(f"ClassRepository : GetLiveClassDetail : {str(e)}")
        raise e


#---------------------------------------------------------
# District APIs Helper Functions
#---------------------------------------------------------

def get_all_districts(offset, limit):
    """Get all districts with pagination"""
    logger.info(f"DistrictRepository : GetAllDistrict : Started")
    
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
        logger.error(f"DistrictRepository : GetAllDistrict : {str(e)}")
        raise e

def save_district(district_data):
    """Save or update district"""
    logger.info(f"DistrictRepository : SaveDistrict : Started")
    
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
        logger.error(f"DistrictRepository : SaveDistrict : {str(e)}")
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
        logger.error(f"DistrictRepository : get_district_by_id : {str(e)}")
        raise e

def check_district_name(name):
    """Check if district name exists"""
    logger.info(f"DistrictRepository : CheckDistrictName : Started")
    
    try:
        sql = "SELECT Name FROM District WHERE Name = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [name])
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"DistrictRepository : CheckDistrictName : {str(e)}")
        raise e

#---------------------------------------------------------

#---------------------------------------------------------
# Dashboard APIs Helper Functions
#---------------------------------------------------------

def get_class_count_by_month(center_id, start_date, end_date):
    """Get class count by month for a center"""
    logger.info(f"DashboardRepository : GetClassCountByMonth : Started")
    
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
        logger.error(f"DashboardRepository : GetClassCountByMonth : {str(e)}")
        raise e

def get_total_gender_ratio_by_center_id(center_id, start_date, end_date):
    """Get total gender ratio by center ID"""
    logger.info(f"DashboardRepository : GetTotalGenderRatioByCenterId : Started")
    
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
        logger.error(f"DashboardRepository : GetTotalGenderRatioByCenterId : {str(e)}")
        raise e

def get_total_student_of_class(center_id, start_date, end_date):
    """Get total student of class by center"""
    logger.info(f"DashboardRepository : GetTotalStudentOfClass : Started")
    
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
        logger.error(f"DashboardRepository : GetTotalStudentOfClass : {str(e)}")
        raise e

def get_center_detail_by_month(center_id, month, year):
    """Get center detail by month and year"""
    logger.info(f"DashboardRepository : GetCenterDetailByMonth : Started")
    
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
        logger.error(f"DashboardRepository : GetCenterDetailByMonth : {str(e)}")
        raise e

def get_total_bpl(center_id, start_date, end_date):
    """Get total BPL students by center"""
    logger.info(f"DashboardRepository : GetTotalBpl : Started")
    
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
        logger.error(f"DashboardRepository : GetTotalBpl : {str(e)}")
        raise e

def get_total_student_category_of_class(center_id, start_date, end_date):
    """Get total student category of class"""
    logger.info(f"DashboardRepository : GetTotalStudentCategoryOfClass : Started")
    
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
        logger.error(f"DashboardRepository : GetTotalStudentCategoryOfClass : {str(e)}")
        raise e

def get_user_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get user by filter"""
    logger.info(f"DashboardRepository : GetUserByFilter : Started")
    
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
        logger.error(f"DashboardRepository : GetUserByFilter : {str(e)}")
        raise e

def get_total_bpl_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get total BPL by filter"""
    logger.info(f"DashboardRepository : GetTotalBplByFilter : Started")
    
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
        logger.error(f"DashboardRepository : GetTotalBplByFilter : {str(e)}")
        raise e

def get_total_gender_ratio_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get total gender ratio by filter"""
    logger.info(f"DashboardRepository : GetTotalGenderRatioByFilter : Started")
    
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
        logger.error(f"DashboardRepository : GetTotalGenderRatioByFilter : {str(e)}")
        raise e

def get_total_student_category_of_class_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get total student category of class by filter"""
    logger.info(f"DashboardRepository : GetTotalStudentCategoryOfClassByFilter : Started")
    
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
        logger.error(f"DashboardRepository : GetTotalStudentCategoryOfClassByFilter : {str(e)}")
        raise e

def get_total_student_grade_of_class_by_filter(district_id, vidhan_sabha_id, panchayta_id, village_id, start_date, end_date):
    """Get total student grade of class by filter"""
    logger.info(f"DashboardRepository : GetTotalStudenGradetOfClassByFilter : Started")
    
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
        logger.error(f"DashboardRepository : GetTotalStudenGradetOfClassByFilter : {str(e)}")
        raise e

def get_district_of_center_by_filter(district_id, vidhan_sabha_id, start_date, end_date):
    """Get district of center by filter"""
    logger.info(f"DashboardRepository : GetDistrictOfCenterByFilter : Started")
    
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
        logger.error(f"DashboardRepository : GetDistrictOfCenterByFilter : {str(e)}")
        raise e

def get_student_attendance_by_percentage():
    """Get student attendance by percentage"""
    logger.info(f"DashboardRepository : GetStudentAttendanceByPercentage : Started")
    
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
        logger.error(f"DashboardRepository : GetStudentAttendanceByPercentage : {str(e)}")
        raise e

#---------------------------------------------------------
# Holidays APIs Helper Functions
#---------------------------------------------------------

def save_holidays(holidays_data):
    """Save or update holidays"""
    logger.info(f"HolidaysRepository : SaveHolidays : Started")
    
    try:
        holiday_id = holidays_data.get('Id', 0)
        center_ids = holidays_data.get('ListCenterIds', [])
        
        with connection.cursor() as cursor:
            if holiday_id > 0:
                # Get existing holidays with same name
                existing_sql = """
                    SELECT Id, CenterId, StartDate, EndDate, Name, Status, CreatedBy
                    FROM Holidays
                    WHERE Name = %s
                """
                cursor.execute(existing_sql, [holidays_data.get('Name')])
                existing_rows = cursor.fetchall()
                
                existing_center_ids = [row[1] for row in existing_rows]
                
                # Remove holidays that are not in the new list
                center_ids_to_remove = [cid for cid in existing_center_ids if cid not in center_ids]
                if center_ids_to_remove:
                    remove_sql = """
                        DELETE FROM Holidays 
                        WHERE Name = %s AND CenterId IN ({})
                    """.format(','.join(['%s'] * len(center_ids_to_remove)))
                    params = [holidays_data.get('Name')] + center_ids_to_remove
                    cursor.execute(remove_sql, params)
                
                # Add new holidays
                center_ids_to_add = [cid for cid in center_ids if cid not in existing_center_ids]
                for center_id in center_ids_to_add:
                    insert_sql = """
                        INSERT INTO Holidays (
                            StartDate, EndDate, Name, Status, CenterId, CreatedOn, CreatedBy
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, [
                        holidays_data.get('StartDate'),
                        holidays_data.get('EndDate'),
                        holidays_data.get('Name'),
                        holidays_data.get('Status'),
                        center_id,
                        datetime.now(),
                        holidays_data.get('CreatedBy')
                    ])
                
                # Update existing holidays
                for center_id in existing_center_ids:
                    if center_id in center_ids:
                        update_sql = """
                            UPDATE Holidays 
                            SET StartDate = %s, EndDate = %s, Name = %s, Status = %s
                            WHERE Name = %s AND CenterId = %s
                        """
                        cursor.execute(update_sql, [
                            holidays_data.get('StartDate'),
                            holidays_data.get('EndDate'),
                            holidays_data.get('Name'),
                            holidays_data.get('Status'),
                            holidays_data.get('Name'),
                            center_id
                        ])
                        
            else:
                # Insert new holidays
                for center_id in center_ids:
                    insert_sql = """
                        INSERT INTO Holidays (
                            StartDate, EndDate, Name, Status, CenterId, CreatedOn, CreatedBy
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, [
                        holidays_data.get('StartDate'),
                        holidays_data.get('EndDate'),
                        holidays_data.get('Name'),
                        holidays_data.get('Status'),
                        center_id,
                        datetime.now(),
                        holidays_data.get('CreatedBy')
                    ])
        
        logger.info(f"HolidaysRepository : SaveHolidays : End")
        return {'status': True, 'message': 'Holidays saved successfully'}
        
    except Exception as e:
        logger.error(f"HolidaysRepository : SaveHolidays : {str(e)}")
        raise e

def get_all_holidays_by_teacher_id(teacher_id):
    """Get all holidays by teacher ID"""
    logger.info(f"HolidaysRepository : GetAllHolidaysByTeacherId : Started")
    
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
        logger.error(f"HolidaysRepository : GetAllHolidaysByTeacherId : {str(e)}")
        raise e

def get_all_holidays_by_year(year):
    """Get all holidays by year"""
    logger.info(f"HolidaysRepository : GetAllHolidaysByYear : Started")
    
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
        logger.error(f"HolidaysRepository : GetAllHolidaysByYear : {str(e)}")
        raise e

def get_all_holidays_by_center_id(center_id):
    """Get all holidays by center ID"""
    logger.info(f"HolidaysRepository : GetAllHolidaysByCenterId : Started")
    
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
        logger.error(f"HolidaysRepository : GetAllHolidaysByCenterId : {str(e)}")
        raise e

def get_all_holidays(status, user_id=0):
    """Get all holidays with optional status and user filter"""
    logger.info(f"HolidaysRepository : GetAllHolidays : Started")
    
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
        logger.error(f"HolidaysRepository : GetAllHolidays : {str(e)}")
        raise e

def delete_holiday_by_id(holiday_id):
    """Delete holiday by ID"""
    logger.info(f"HolidaysRepository : DeleteHolidayById : Started")
    
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
        logger.error(f"HolidaysRepository : DeleteHolidayById : {str(e)}")
        raise e


#---------------------------------------------------------
# Panchayat APIs Helper Functions
#---------------------------------------------------------

def get_all_panchayats(offset, limit):
    """Get all panchayats with pagination"""
    logger.info(f"PanchayatRepository : GetAllPanchayat : Started")
    
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
        logger.error(f"PanchayatRepository : GetAllPanchayat : {str(e)}")
        raise e

def save_panchayat(panchayat_data):
    """Save or update panchayat"""
    logger.info(f"PanchayatRepository : SavePanchayat : Started")
    
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
        logger.error(f"PanchayatRepository : SavePanchayat : {str(e)}")
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
        logger.error(f"PanchayatRepository : get_panchayat_by_id : {str(e)}")
        raise e

def get_panchayat_by_district_and_vidhan_sabha_id(district_id, vidhan_sabha_id):
    """Get panchayat by district and vidhan sabha ID"""
    logger.info(f"PanchayatRepository : GetPanchayatByDistrictAndVidhanSabhaId : Started")
    
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
        logger.error(f"PanchayatRepository : GetPanchayatByDistrictAndVidhanSabhaId : {str(e)}")
        raise e

def check_panchayat_name(name):
    """Check if panchayat name exists"""
    logger.info(f"PanchayatRepository : CheckPanchayatName : Started")
    
    try:
        sql = "SELECT Name FROM Panchayat WHERE Name = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, [name])
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"PanchayatRepository : CheckPanchayatName : {str(e)}")
        raise e