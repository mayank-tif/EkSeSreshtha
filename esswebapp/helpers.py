"""Common helpers for the web app (esswebapp).

Shared business logic for the web application, kept separate from the
APIS app helpers so each can evolve independently.

Current helpers:
    - save_center_web: create/update Center with assignment sync
      (optional lat/lng, ORM-based, session auth)
"""
import logging
import uuid
from datetime import datetime
from decimal import Decimal

from django.db import transaction

from APIS.models import Center, Teacher, RegionalAdmin, CenterAssignUser

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
