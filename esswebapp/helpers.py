"""Common helpers for the web app (esswebapp).

Shared business logic for the web application, kept separate from the
APIS app helpers so each can evolve independently.

Current helpers:
    - save_center_web: create/update Center with assignment sync
      (optional lat/lng, ORM-based, session auth)
"""
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction

from APIS.models import Center, Teacher, RegionalAdmin, CenterAssignUser, Student, StudentAttendance, User
from django.db.models import Count

logger = logging.getLogger(__name__)


def _get_web_user_id(request):
    """Get current user id from the web session (set by LoginRequiredMixin)."""
    web_user = getattr(request, 'web_user', None) or {}
    return web_user.get('user_id')


def save_center_web(center_data, request):
    """Create or update a Center for the web app.

    Args:
        center_data: dict with PascalCase keys (matches APIS helper contract):
            Id (0 = create, >0 = update), CenterName, Address, DistrictId,
            VidhanSabhaId, PanchayatId, VillageId, Latitude, Longitude,
            AssignedTeachers, AssignedRegionalAdmin, StartedDate, ClassStatus
        request: Django request with request.web_user session dict.

    Returns:
        The saved Center ORM instance, or None if update target not found.
    """
    logger.info("WebCenterHelper : SaveCenter : Started")

    center_id = int(center_data.get('Id', 0) or 0)
    current_user_id = _get_web_user_id(request)

    with transaction.atomic():
        if center_id > 0:
            center = _update_center(center_id, center_data, current_user_id)
            if center is None:
                return None
        else:
            center = _create_center(center_data, current_user_id)

    return center


def _update_center(center_id, center_data, current_user_id):
    """Update an existing center. Preserves Status and ClassStatus."""
    try:
        center = Center.objects.get(id=center_id, status=True)
    except Center.DoesNotExist:
        logger.error(f"WebCenterHelper : Center not found with ID: {center_id}")
        return None
    
    print("update ", center_data, center_id)

    old_teacher_id = center.assigned_teachers
    old_regional_admin_id = center.assigned_regional_admin

    # Update scalar fields only when provided
    if center_data.get('CenterName') is not None:
        center.center_name = center_data['CenterName']
    if center_data.get('Address') is not None:
        center.address = center_data['Address']
    if center_data.get('AssignedTeachers') is not None:
        center.assigned_teachers = center_data['AssignedTeachers']
    if center_data.get('AssignedRegionalAdmin') is not None:
        center.assigned_regional_admin = center_data['AssignedRegionalAdmin']
    if center_data.get('StartedDate') is not None:
        center.started_date = center_data['StartedDate']
    if center_data.get('VidhanSabhaId') is not None:
        center.vidhan_sabha_id = center_data['VidhanSabhaId']
    if center_data.get('DistrictId') is not None:
        center.district_id = center_data['DistrictId']
    if center_data.get('PanchayatId') is not None:
        center.panchayat_id = center_data['PanchayatId']
    if center_data.get('VillageId') is not None:
        center.village_id = center_data['VillageId']

    # Latitude/longitude are OPTIONAL for the web app.
    # Only touch location fields when BOTH are explicitly provided;
    # otherwise preserve the existing location data/status.
    latitude = center_data.get('Latitude')
    longitude = center_data.get('Longitude')
    if latitude is not None and longitude is not None:
        center.latitude = Decimal(str(latitude))
        center.longitude = Decimal(str(longitude))
        center.location_status = 'VERIFIED'
        center.location_verified_at = datetime.now()
        if current_user_id:
            center.location_verified_by_id = current_user_id

    center.updated_on = datetime.now()
    center.updated_by = current_user_id
    center.save()

    # Sync teacher / regional-admin assignment statuses when changed
    if old_teacher_id != center.assigned_teachers:
        _unassign_old_teacher(old_teacher_id, center_id, current_user_id)
        _assign_new_teacher(center, current_user_id)

    if old_regional_admin_id != center.assigned_regional_admin:
        _unassign_old_regional_admin(old_regional_admin_id, center_id, current_user_id)
        _assign_new_regional_admin(center, current_user_id)

    return center


def _create_center(center_data, current_user_id):
    print("create", center_data)
    """Create a new center."""
    latitude = center_data.get('Latitude')
    longitude = center_data.get('Longitude')
    has_location = latitude is not None and longitude is not None

    teacher_user_id = center_data.get('AssignedTeachers')
    regional_admin_user_id = center_data.get('AssignedRegionalAdmin')
    print('teacher_user_id', teacher_user_id, regional_admin_user_id)

    center = Center(
        center_guid_id=str(uuid.uuid4()),
        center_name=center_data.get('CenterName'),
        assigned_teachers=teacher_user_id,
        assigned_regional_admin=regional_admin_user_id,
        started_date=center_data.get('StartedDate'),
        vidhan_sabha_id=center_data.get('VidhanSabhaId'),
        district_id=center_data.get('DistrictId'),
        panchayat_id=center_data.get('PanchayatId'),
        village_id=center_data.get('VillageId'),
        status=True,
        class_status=center_data.get('ClassStatus', False),
        created_date=datetime.now(),
        created_on=datetime.now(),
        created_by=current_user_id,
        latitude=Decimal(str(latitude)) if has_location else None,
        longitude=Decimal(str(longitude)) if has_location else None,
        location_status="VERIFIED" if has_location else "PENDING",
        location_verified_at=datetime.now() if has_location else None,
        location_verified_by_id=current_user_id if has_location else None,
        address=center_data.get('Address')
    )
    center.save()

    if teacher_user_id:
        _assign_new_teacher(center, current_user_id)
    if regional_admin_user_id:
        _assign_new_regional_admin(center, current_user_id)

    return center


# ── Assignment helpers ────────────────────────────────────────────

def _unassign_old_teacher(old_teacher_id, center_id, current_user_id):
    """Clear assignment flags on the previously assigned teacher (if no other center)."""
    if not old_teacher_id:
        return
    try:
        old_teacher = Teacher.objects.filter(user_id=old_teacher_id, status=True).first()
        if old_teacher:
            other_center = Center.objects.filter(
                assigned_teachers=old_teacher_id,
                status=True
            ).exclude(id=center_id).first()
            if not other_center:
                old_teacher.assigned_teacher_status = False
                old_teacher.updated_on = datetime.now()
                old_teacher.updated_by = current_user_id
                old_teacher.save()
    except Exception as e:
        logger.error(f"WebCenterHelper : Error updating old teacher status: {str(e)}")


def _assign_new_teacher(center, current_user_id):
    """Set assignment flags on the newly assigned teacher and log history."""
    if not center.assigned_teachers:
        return
    try:
        new_teacher = Teacher.objects.filter(user_id=center.assigned_teachers, status=True).first()
        if new_teacher:
            new_teacher.assigned_teacher_status = True
            new_teacher.updated_on = datetime.now()
            new_teacher.updated_by = current_user_id
            new_teacher.center = center
            new_teacher.save()

            if new_teacher.user:
                CenterAssignUser.objects.create(
                    center_id=center.id,
                    users_id=new_teacher.user.id,
                    date=datetime.now(),
                    status=True,
                    created_by=current_user_id,
                    created_on=datetime.now()
                )
    except Exception as e:
        logger.error(f"WebCenterHelper : Error updating new teacher status: {str(e)}")


def _unassign_old_regional_admin(old_regional_admin_id, center_id, current_user_id):
    """Clear assignment flags on the previously assigned regional admin (if no other center)."""
    if not old_regional_admin_id:
        return
    try:
        old_ra = RegionalAdmin.objects.filter(user_id=old_regional_admin_id, status=True).first()
        if old_ra:
            other_center = Center.objects.filter(
                assigned_regional_admin=old_regional_admin_id,
                status=True
            ).exclude(id=center_id).first()
            if not other_center:
                old_ra.assigned_regional_admin_status = False
                old_ra.updated_on = datetime.now()
                old_ra.updated_by = current_user_id
                old_ra.save()
    except Exception as e:
        logger.error(f"WebCenterHelper : Error updating old regional admin status: {str(e)}")


def _assign_new_regional_admin(center, current_user_id):
    """Set assignment flags on the newly assigned regional admin and log history."""
    if not center.assigned_regional_admin:
        return
    try:
        new_ra = RegionalAdmin.objects.filter(user_id=center.assigned_regional_admin, status=True).first()
        if new_ra:
            new_ra.assigned_regional_admin_status = True
            new_ra.updated_on = datetime.now()
            new_ra.updated_by = current_user_id
            new_ra.save()

            if new_ra.user:
                CenterAssignUser.objects.create(
                    center_id=center.id,
                    users_id=new_ra.user.id,
                    date=datetime.now(),
                    status=True,
                    created_by=current_user_id,
                    created_on=datetime.now()
                )
    except Exception as e:
        logger.error(f"WebCenterHelper : Error updating new regional admin status: {str(e)}")


# ==================================================================
# CENTER ATTENDANCE HELPERS
# ==================================================================

def get_center_attendance_data(center_ids, attendance_date=None):
    """
    Get attendance data for a list of centers on a specific date.
    
    Uses StudentAttendance records (created by API attendance marking)
    rather than ClassModel records.
    
    Args:
        center_ids: List of center IDs
        attendance_date: date object or None (defaults to today)
    
    Returns:
        dict mapping center_id -> {
            'total_students': int (active students in center),
            'present_students': int (attendance records for date),
            'attendance_pct': int (percentage),
            'teacher_name': str or None,
            'regional_admin_name': str or None,
        }
    """
    logger.info(f"WebCenterAttendanceHelper : GetCenterAttendanceData : Started for {len(center_ids)} centers, date={attendance_date}")
    
    if not center_ids:
        return {}
    
    print("center_ids", center_ids, attendance_date)
    
    if attendance_date is None:
        attendance_date = datetime.now().date()
    elif isinstance(attendance_date, str):
        try:
            attendance_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
        except ValueError:
            attendance_date = datetime.now().date()
    
    # 1. Get total enrolled students per center (all students assigned to center, regardless of status)
    student_counts = dict(
        Student.objects.filter(center_id__in=center_ids)
        .values('center_id').annotate(cnt=Count('id'))
        .values_list('center_id', 'cnt')
    )
    print("student_counts", student_counts)
    
    # 2. Get present student count per center from StudentAttendance
    # Count DISTINCT enrolled students who were present
    present_records = StudentAttendance.objects.filter(
        center_id__in=center_ids,
        scan_date__date=attendance_date,
        status=True,
        type=True  # present
    ).values('center_id', 'student_id').distinct()
    
    # Filter to only count students actually enrolled in each center
    enrolled_ids_by_center = {}
    students = Student.objects.filter(center_id__in=center_ids).values('id', 'center_id')
    for s in students:
        enrolled_ids_by_center.setdefault(s['center_id'], set()).add(s['id'])
    
    present_counts = {}
    for r in present_records:
        c_id = r['center_id']
        stu_id = r['student_id']
        if c_id in enrolled_ids_by_center and stu_id in enrolled_ids_by_center[c_id]:
            present_counts[c_id] = present_counts.get(c_id, 0) + 1
    
    print("present_counts", present_counts)
    
    # 3. Get teacher and regional admin names in bulk
    user_ids = []
    centers = Center.objects.filter(id__in=center_ids).select_related()
    for c in centers:
        if c.assigned_teachers:
            user_ids.append(c.assigned_teachers)
        if c.assigned_regional_admin:
            user_ids.append(c.assigned_regional_admin)
    
    name_map = {}
    if user_ids:
        name_map = dict(User.objects.filter(id__in=set(user_ids)).values_list('id', 'name'))
    
    # 4. Build result
    result = {}
    for center_id in center_ids:
        total = student_counts.get(center_id, 0)
        present = present_counts.get(center_id, 0)
        pct = int((present / total * 100)) if total > 0 else 0
        
        center = Center.objects.filter(id=center_id).first()
        teacher_name = None
        regional_admin_name = None
        if center:
            teacher_name = name_map.get(center.assigned_teachers)
            regional_admin_name = name_map.get(center.assigned_regional_admin)
        
        result[center_id] = {
            'total_students': total,
            'present_students': present,
            'attendance_pct': pct,
            'teacher_name': teacher_name,
            'regional_admin_name': regional_admin_name,
        }
    
    logger.info(f"WebCenterAttendanceHelper : GetCenterAttendanceData : End - {len(result)} centers")
    return result


def get_center_monthly_attendance(center_ids, year, month):
    """
    Get monthly attendance summary for centers using single query.
    
    Args:
        center_ids: List of center IDs
        year: Year (e.g., 2026)
        month: Month (1-12)
    
    Returns:
        dict mapping center_id -> {
            'total_students': int (enrolled students),
            'present_students': int (distinct students present at least once in month),
            'attendance_pct': int (percentage),
            'working_days': int (Mon-Sat in month up to today),
            'teacher_name': str,
            'regional_admin_name': str,
        }
    """
    from calendar import monthrange
    from datetime import datetime
    print("get_center_monthly_attendance", center_ids, year, month)
    
    logger.info(f"WebCenterAttendanceHelper : GetCenterMonthlyAttendance : Started for {len(center_ids)} centers, {year}-{month}")
    
    if not center_ids:
        return {}
    
    start_date = datetime(year, month, 1).date()
    days_in_month = monthrange(year, month)[1]
    end_date = datetime(year, month, days_in_month).date()
    today = datetime.now().date()
    if end_date > today:
        end_date = today
    
    # Count working days (Mon-Sat) in the period
    working_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 6:  # Mon-Sat
            working_days += 1
        current += timedelta(days=1)
    
    # 1. Get total enrolled students per center
    student_counts = dict(
        Student.objects.filter(center_id__in=center_ids, status=True)
        .values('center_id').annotate(cnt=Count('id'))
        .values_list('center_id', 'cnt')
    )
    print("student_counts", student_counts)
    
    # 2. Get daily present student counts per center (sum of daily present students)
    daily_present = StudentAttendance.objects.filter(
        center_id__in=center_ids,
        scan_date__date__gte=start_date,
        scan_date__date__lte=end_date,
        status=True,
        type=True
    ).values('center_id', 'scan_date__date').annotate(
        daily_present=Count('student_id', distinct=True)
    )
    print("daily_present", list(daily_present))
    
    # Filter to only count students actually enrolled in each center
    enrolled_ids_by_center = {}
    students = Student.objects.filter(center_id__in=center_ids, status=True).values('id', 'center_id')
    for s in students:
        enrolled_ids_by_center.setdefault(s['center_id'], set()).add(s['id'])
    
    # Sum up daily present counts per center
    present_counts = {}
    for r in daily_present:
        c_id = r['center_id']
        # We need to verify students are enrolled - but since we filter by center_id in query,
        # and attendance records already have center_id, they should be enrolled
        present_counts[c_id] = present_counts.get(c_id, 0) + r['daily_present']
    
    # 3. Get teacher and regional admin names
    user_ids = []
    centers = Center.objects.filter(id__in=center_ids, status=True).select_related()
    for c in centers:
        if c.assigned_teachers:
            user_ids.append(c.assigned_teachers)
        if c.assigned_regional_admin:
            user_ids.append(c.assigned_regional_admin)
    
    name_map = {}
    if user_ids:
        name_map = dict(User.objects.filter(id__in=set(user_ids), status=True).values_list('id', 'name'))
    
    # 4. Build result
    result = {}
    for center_id in center_ids:
        total = student_counts.get(center_id, 0)
        present = present_counts.get(center_id, 0)
        # Percentage = total student-days present / (total students * working_days) * 100
        max_possible = total * working_days
        pct = int((present / max_possible * 100)) if max_possible > 0 else 0
        
        center = Center.objects.filter(id=center_id, status=True).first()
        teacher_name = name_map.get(center.assigned_teachers) if center else None
        regional_admin_name = name_map.get(center.assigned_regional_admin) if center else None
        
        result[center_id] = {
            'total_students': total,
            'present_students': present,
            'attendance_pct': min(pct, 100),
            'working_days': working_days,
            'teacher_name': teacher_name,
            'regional_admin_name': regional_admin_name,
        }
    
    logger.info(f"WebCenterAttendanceHelper : GetCenterMonthlyAttendance : End - {len(result)} centers")
    return result


# ==================================================================
# STUDENT ATTENDANCE HISTORY HELPERS
# ==================================================================

def get_student_attendance_history(student_id, start_date=None, end_date=None):
    """
    Get attendance history for a specific student.
    
    Args:
        student_id: Student ID
        start_date: date object or None (defaults to 30 days ago)
        end_date: date object or None (defaults to today)
    
    Returns:
        List of dicts with 'date' and 'status' (Present/Absent)
    """
    logger.info(f"WebStudentAttendanceHelper : GetStudentAttendanceHistory : Started for student={student_id}")
    
    if start_date is None:
        start_date = datetime.now().date() - timedelta(days=30)
    elif isinstance(start_date, str):
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            start_date = datetime.now().date() - timedelta(days=30)
    
    if end_date is None:
        end_date = datetime.now().date()
    elif isinstance(end_date, str):
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            end_date = datetime.now().date()
    
    # Get attendance records for this student in the date range
    records = StudentAttendance.objects.filter(
        student_id=student_id,
        scan_date__date__gte=start_date,
        scan_date__date__lte=end_date,
        status=True
    ).values('scan_date', 'type').order_by('scan_date')
    
    # Group by date - if multiple records for same day, consider Present if any is Present
    attendance_by_date = {}
    for record in records:
        date_key = record['scan_date'].date()
        if date_key not in attendance_by_date:
            attendance_by_date[date_key] = 'Absent'
        if record['type'] is True or record['type'] == 'True':  # Present
            attendance_by_date[date_key] = 'Present'
    
    # Convert to list format
    result = []
    for date_key, status in sorted(attendance_by_date.items()):
        result.append({
            'date': date_key,
            'status': status
        })
    
    logger.info(f"WebStudentAttendanceHelper : GetStudentAttendanceHistory : End - {len(result)} records")
    return result


def get_student_monthly_attendance(student_id, year, month):
    """
    Get attendance summary for a specific student for a given month.
    
    Args:
        student_id: Student ID
        year: Year (e.g., 2026)
        month: Month (1-12)
    
    Returns:
        dict with 'present', 'absent', 'total_days', 'working_days', 'percentage'
    """
    from calendar import monthrange
    
    start_date = datetime(year, month, 1).date()
    days_in_month = monthrange(year, month)[1]
    end_date = datetime(year, month, days_in_month).date()
    today = datetime.now().date()
    if end_date > today:
        end_date = today
    
    # Count working days (Mon-Sat) in the period
    working_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 6:  # Mon-Sat
            working_days += 1
        current += timedelta(days=1)
    
    history = get_student_attendance_history(student_id, start_date, end_date)
    
    present = sum(1 for r in history if r['status'] == 'Present')
    absent = sum(1 for r in history if r['status'] == 'Absent')
    total_recorded = present + absent
    
    # Percentage based on working days, not just recorded days
    pct = int((present / working_days * 100)) if working_days > 0 else 0
    
    return {
        'present': present,
        'absent': absent,
        'total_days': total_recorded,
        'working_days': working_days,
        'percentage': min(pct, 100)
    }


def get_student_daily_attendance(student_id, year, month):
    """
    Get day-wise attendance for a specific student for a given month.
    
    Args:
        student_id: Student ID
        year: Year (e.g., 2026)
        month: Month (1-12)
    
    Returns:
        List of dicts with 'day' and 'status' for each day in the month
    """
    from calendar import monthrange
    
    days_in_month = monthrange(year, month)[1]
    today = datetime.now().date()
    
    history = get_student_attendance_history(student_id,
        datetime(year, month, 1).date(),
        datetime(year, month, days_in_month).date()
    )
    
    # Build lookup
    attendance_map = {r['date']: r['status'] for r in history}
    
    result = []
    for day in range(1, days_in_month + 1):
        date = datetime(year, month, day).date()
        if date > today:
            continue  # Skip future dates
        if date.weekday() == 6:  # Skip Sundays
            continue
        
        status = attendance_map.get(date, 'Absent')
        result.append({
            'day': day,
            'date': date,
            'status': status
        })
    
    return result


