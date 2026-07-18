from datetime import datetime

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers
from .models import *
from .utils import mobile_number_validation


class GenerateAppTokenSerializer(serializers.Serializer):
    deviceid = serializers.CharField(max_length=250, required=True, allow_blank=False)



def format_dotnet_datetime(value):
    if not value:
        return None
    if isinstance(value, str):
        return value
    hour = value.strftime("%I").lstrip("0") or "0"
    return f"{value.month}/{value.day}/{value.year} {hour}:{value:%M:%S %p}"


def required_char():
    return serializers.CharField(required=True, allow_blank=False)


def optional_char():
    return serializers.CharField(required=False, allow_blank=True, allow_null=True)


def required_int():
    return serializers.IntegerField(required=True)


def optional_int():
    return serializers.IntegerField(required=False, allow_null=True)


def required_bool():
    return serializers.BooleanField(required=True)


def optional_bool():
    return serializers.BooleanField(required=False, allow_null=True)


class FlexibleDateTimeField(serializers.DateTimeField):
    dotnet_input_formats = ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y")

    def to_internal_value(self, value):
        if value in ("", None):
            if self.required:
                self.fail("required")
            return None
        try:
            return super().to_internal_value(value)
        except serializers.ValidationError:
            parsed = parse_datetime(str(value))
            if parsed:
                return parsed
            parsed_date = parse_date(str(value))
            if parsed_date:
                return datetime.combine(parsed_date, datetime.min.time())
            for input_format in self.dotnet_input_formats:
                try:
                    return datetime.strptime(str(value), input_format)
                except ValueError:
                    continue
            raise


def required_datetime():
    return FlexibleDateTimeField(required=True)


def optional_datetime():
    return FlexibleDateTimeField(required=False, allow_null=True)


class RequestSerializer(serializers.Serializer):
    foreign_key_fields = {}
    foreign_key_list_fields = {}

    def to_internal_value(self, data):
        """Match ASP.NET Core's case-insensitive form/JSON DTO binding.

        The mobile clients use both ``CenterId`` and ``centerId`` (and the
        occasional all-lowercase form key).  DRF normally treats those as
        different fields, whereas the source API does not.
        """
        if data is not None:
            supplied = data.lists() if hasattr(data, "lists") else data.items()
            supplied = dict(supplied)
            fields_by_casefold = {name.casefold(): name for name in self.fields}
            normalised = {}
            for key, value in supplied.items():
                field_name = fields_by_casefold.get(str(key).casefold(), key)
                # QueryDict.list() values are only needed for ListField inputs.
                if isinstance(value, (list, tuple)) and not isinstance(self.fields.get(field_name), serializers.ListField):
                    value = value[-1] if value else None
                normalised[field_name] = value
            data = normalised
        return super().to_internal_value(data)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        errors = {}
        for field_name, model in self.foreign_key_fields.items():
            value = attrs.get(field_name)
            if value in (None, ""):
                continue
            if not model.objects.filter(pk=value).exists():
                errors[field_name] = f"{model.__name__} with this id does not exist."
        for field_name, model in self.foreign_key_list_fields.items():
            values = attrs.get(field_name) or []
            existing_ids = set(model.objects.filter(pk__in=values).values_list("id", flat=True))
            missing_ids = [value for value in values if value not in existing_ids]
            if missing_ids:
                errors[field_name] = f"{model.__name__} ids do not exist: {missing_ids}"
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class PaginationQuerySerializer(RequestSerializer):
    offset = optional_int()
    limit = optional_int()


class IdQuerySerializer(RequestSerializer):
    id = required_int()
    
    
# serializers.py

class RoleSerializer(serializers.Serializer):
    Id = serializers.IntegerField(required=False, allow_null=True)
    RoleName = serializers.CharField(required=True)
    RoleCode = serializers.CharField(required=True)
    Description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Status = serializers.BooleanField(required=False, allow_null=True)
    CreatedOn = serializers.DateTimeField(required=False, allow_null=True)
    UpdatedOn = serializers.DateTimeField(required=False, allow_null=True)
    CreatedBy = serializers.IntegerField(required=False, allow_null=True)
    UpdatedBy = serializers.IntegerField(required=False, allow_null=True)


class UserSaveRequestSerializer(RequestSerializer):
    foreign_key_fields = {
        "RoleId": Role,
    }
    
    Id = serializers.IntegerField(required=False, allow_null=True)
    EnrolmentRollId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Name = serializers.CharField(required=True)
    Password = serializers.CharField(required=True)
    Token = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Email = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    PhoneNumber = serializers.CharField(required=True)
    WhatsApp = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Status = serializers.BooleanField(required=False, allow_null=True)
    Picture = serializers.ImageField(required=False, allow_null=True)
    LastLoginTime = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    DeviceId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    CreatedOn = serializers.DateTimeField(required=False, allow_null=True)
    EnrollmentDate = serializers.DateTimeField(required=False, allow_null=True)
    CreatedBy = serializers.IntegerField(required=False, allow_null=True)
    RoleId = serializers.IntegerField(required=True)


class SuperAdminSaveRequestSerializer(RequestSerializer):
    Id = serializers.IntegerField(required=False, allow_null=True)
    SuperAdminGuidId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    UserId = serializers.IntegerField(required=True)
    Status = serializers.BooleanField(required=False, allow_null=True)
    CreatedOn = serializers.DateTimeField(required=False, allow_null=True)
    CreatedBy = serializers.IntegerField(required=False, allow_null=True)


class RegionalAdminSaveRequestSerializer(RequestSerializer):
    foreign_key_fields = {
        "UserId": User,
        "DistrictId": District,
        "VidhanSabhaId": VidhanSabha,
        "PanchayatId": Panchayat,
        "VillageId": Village,
    }
    
    Id = serializers.IntegerField(required=False, allow_null=True)
    RegionalAdminGuidId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    UserId = serializers.IntegerField(required=True)
    Age = serializers.IntegerField(required=False, allow_null=True)
    Gender = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    DateOfBirth = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Contact = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    FullAddress = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Education = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    GuardianName = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    GuardianNumber = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    AssignedTeacherStatus = serializers.BooleanField(required=False, allow_null=True)
    AssignedRegionalAdminStatus = serializers.BooleanField(required=False, allow_null=True)
    EnrollmentDate = serializers.DateTimeField(required=False, allow_null=True)
    DistrictId = serializers.IntegerField(required=False, allow_null=True)
    VidhanSabhaId = serializers.IntegerField(required=False, allow_null=True)
    PanchayatId = serializers.IntegerField(required=False, allow_null=True)
    VillageId = serializers.IntegerField(required=False, allow_null=True)
    Status = serializers.BooleanField(required=False, allow_null=True)
    CreatedOn = serializers.DateTimeField(required=False, allow_null=True)
    CreatedBy = serializers.IntegerField(required=False, allow_null=True)


class TeacherSaveRequestSerializer(RequestSerializer):
    foreign_key_fields = {
        "UserId": User,
        "DistrictId": District,
        "VidhanSabhaId": VidhanSabha,
        "PanchayatId": Panchayat,
        "VillageId": Village,
        "CenterId": Center,
    }
    
    Id = serializers.IntegerField(required=False, allow_null=True)
    TeacherGuidId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    UserId = serializers.IntegerField(required=True)
    Age = serializers.IntegerField(required=False, allow_null=True)
    Gender = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    DateOfBirth = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Contact = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    FullAddress = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Education = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    GuardianName = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    GuardianNumber = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Count = serializers.IntegerField(required=False, allow_null=True)
    AssignedTeacherStatus = serializers.BooleanField(required=False, allow_null=True)
    AssignedRegionalAdminStatus = serializers.BooleanField(required=False, allow_null=True)
    EnrollmentDate = serializers.DateTimeField(required=False, allow_null=True)
    DistrictId = serializers.IntegerField(required=False, allow_null=True)
    VidhanSabhaId = serializers.IntegerField(required=False, allow_null=True)
    PanchayatId = serializers.IntegerField(required=False, allow_null=True)
    VillageId = serializers.IntegerField(required=False, allow_null=True)
    CenterId = serializers.IntegerField(required=False, allow_null=True)
    Status = serializers.BooleanField(required=False, allow_null=True)
    CreatedOn = serializers.DateTimeField(required=False, allow_null=True)
    CreatedBy = serializers.IntegerField(required=False, allow_null=True)


class SuperAdminDtoSerializer(serializers.Serializer):
    Id = serializers.IntegerField()
    SuperAdminGuidId = serializers.CharField(allow_null=True, required=False)
    UserId = serializers.IntegerField()
    Name = serializers.CharField(allow_null=True, required=False)
    Email = serializers.CharField(allow_null=True, required=False)
    PhoneNumber = serializers.CharField(allow_null=True, required=False)
    Status = serializers.BooleanField(allow_null=True, required=False)
    CreatedOn = serializers.DateTimeField(allow_null=True, required=False)
    CreatedBy = serializers.IntegerField(allow_null=True, required=False)


    
# Announcement Serializers-----------------------------------------------------------------------------------------------
class AnnouncementSaveAnnouncementRequestSerializer(RequestSerializer):
    Id = optional_int()
    Title = required_char()
    Description = required_char()
    ImageFile = serializers.ListField(child=serializers.FileField(), required=True)
    Image = optional_char()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()

class AnnouncementDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    title = serializers.CharField(source='Title', allow_null=True, required=False)
    description = serializers.CharField(source='Description', allow_null=True, required=False)
    image = serializers.CharField(source='Image', allow_null=True, required=False)
    createdOn = serializers.DateTimeField(source='CreatedOn', allow_null=True, required=False)
    createdBy = serializers.IntegerField(source='CreatedBy', allow_null=True, required=False)

# Center serializers ------------------------------------------------------------------------------------------------------------------------------
class CenterGetAllCentersQuerySerializer(serializers.Serializer):
    userId = serializers.IntegerField(required=False, default=0)
    type = serializers.IntegerField(required=False, default=0)
    

class AllCenterDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    centerName = serializers.CharField(allow_null=True, required=False)
    date = serializers.CharField(allow_null=True, required=False)
    classDate = serializers.DateTimeField(allow_null=True, required=False)
    classEndDate = serializers.DateTimeField(allow_null=True, required=False)
    classStatus = serializers.BooleanField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    districtName = serializers.CharField(allow_null=True, required=False)
    vidhanSabhaName = serializers.CharField(allow_null=True, required=False)
    totalPresentStudents = serializers.IntegerField(allow_null=True, required=False)
    totalActiveStudents = serializers.IntegerField(allow_null=True, required=False)
    totalStudents = serializers.IntegerField(allow_null=True, required=False)
    panchayatName = serializers.CharField(allow_null=True, required=False)
    villageName = serializers.CharField(allow_null=True, required=False)
    vidhanSabhaId = serializers.IntegerField(required=False)
    villageId = serializers.IntegerField(allow_null=True, required=False)
    districtId = serializers.IntegerField(required=False)
    panchayatId = serializers.IntegerField(required=False)
    assignedTeacher = serializers.IntegerField(allow_null=True, required=False)
    teacherName = serializers.CharField(allow_null=True, required=False)
    assignedRegionalAdmin = serializers.IntegerField(allow_null=True, required=False)
    regionalAdminName = serializers.CharField(allow_null=True, required=False)
    
class CenterGetAllCentersByStatusQuerySerializer(serializers.Serializer):
    status = serializers.IntegerField(required=True)
    userId = serializers.IntegerField(required=True)
    
class AllCenterStatusDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    centerName = serializers.CharField(source="center_name", allow_null=True, required=False)
    date = serializers.CharField(allow_null=True, required=False)
    classStartDate = serializers.CharField(source="class_start_date", allow_null=True, required=False)
    classEndDate = serializers.CharField(source="class_end_date", allow_null=True, required=False)
    classStatus = serializers.BooleanField(source="class_status", allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    districtName = serializers.CharField(source="district_name", allow_null=True, required=False)
    vidhanSabhaName = serializers.CharField(source="vidhan_sabha_name", allow_null=True, required=False)
    villageName = serializers.CharField(source="village_name", allow_null=True, required=False)
    totalPresentStudents = serializers.IntegerField(source="total_present_students", allow_null=True, required=False)
    totalStudents = serializers.IntegerField(source="total_students", allow_null=True, required=False)
    panchayatName = serializers.CharField(source="panchayat_name", allow_null=True, required=False)
    vidhanSabhaId = serializers.IntegerField(source="vidhan_sabha_id", required=False)
    districtId = serializers.IntegerField(source="district_id", required=False)
    panchayatId = serializers.IntegerField(source="panchayat_id", required=False)
    assignedTeacher = serializers.IntegerField(source="assigned_teacher", allow_null=True, required=False)
    teacherName = serializers.CharField(source="teacher_name", allow_null=True, required=False)
    assignedRegionalAdmin = serializers.IntegerField(source="assigned_regional_admin", allow_null=True, required=False)
    regionalAdminName = serializers.CharField(source="regional_admin_name", allow_null=True, required=False)


class CenterSaveCenterRequestSerializer(RequestSerializer):
    foreign_key_fields = {
        "AssignedTeachers": User,
        "AssignedRegionalAdmin": User,
        "VidhanSabhaId": VidhanSabha,
        "DistrictId": District,
        "PanchayatId": Panchayat,
        "VillageId": Village,
    }

    Id = serializers.IntegerField(required=False, allow_null=True)
    CenterGuidId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    CenterName = serializers.CharField(required=True)
    AssignedTeachers = serializers.IntegerField(required=True)
    AssignedRegionalAdmin = serializers.IntegerField(required=True)
    StartedDate = serializers.DateTimeField(required=False, allow_null=True)
    VidhanSabhaId = serializers.IntegerField(required=True)
    DistrictId = serializers.IntegerField(required=True)
    PanchayatId = serializers.IntegerField(required=True)
    VillageId = serializers.IntegerField(required=False, allow_null=True)



class CenterDetailDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    centerName = serializers.CharField(source='CenterName', allow_null=True, required=False)
    classStatus = serializers.BooleanField(source='ClassStatus', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    enrollmentDate = serializers.CharField(source='EnrollmentDate', allow_null=True, required=False)
    vidhanSabhaId = serializers.IntegerField(source='VidhanSabhaId')
    districtId = serializers.IntegerField(source='DistrictId')
    panchayatId = serializers.IntegerField(source='PanchayatId')
    villageId = serializers.IntegerField(source='VillageId', allow_null=True, required=False)
    districtName = serializers.CharField(source='DistrictName', allow_null=True, required=False)
    vidhanSabhaName = serializers.CharField(source='VidhanSabhaName', allow_null=True, required=False)
    villageName = serializers.CharField(source='VillageName', allow_null=True, required=False)
    panchayatName = serializers.CharField(source='PanchayatName', allow_null=True, required=False)
    regionalAdminId = serializers.IntegerField(source='RegionalAdminId', allow_null=True, required=False)
    regionalAdminName = serializers.CharField(source='RegionalAdminName', allow_null=True, required=False)
    totalStudents = serializers.IntegerField(source='TotalStudents', allow_null=True, required=False)
    teacher = serializers.DictField(allow_null=True, required=False)

class UserDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True, required=False)
    phoneNumber = serializers.CharField(allow_null=True, required=False)
    picture = serializers.CharField(allow_null=True, required=False)

class CenterAttendanceDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    centerName = serializers.CharField(source='CenterName', allow_null=True, required=False)
    type = serializers.IntegerField(source='Type')
    classStartedDate = serializers.DateTimeField(source='ClassStartedDate', allow_null=True, required=False)
    classEndDate = serializers.DateTimeField(source='ClassEndDate', allow_null=True, required=False)
    totalStudents = serializers.IntegerField(source='TotalStudents', allow_null=True, required=False)
    presentStudents = serializers.IntegerField(source='PresentStudents', allow_null=True, required=False)
    regionalAdminName = serializers.CharField(source='RegionalAdminName', allow_null=True, required=False)
    teacherName = serializers.CharField(source='TeacherName', allow_null=True, required=False)
    startDate = serializers.DateTimeField(source='StartDate', allow_null=True, required=False)
    endDate = serializers.DateTimeField(source='EndDate', allow_null=True, required=False)
    reason = serializers.CharField(source='Reason', allow_null=True, required=False)

class CenterGetAllCenterAttendanceQuerySerializer(RequestSerializer):
    userId = required_int()
    date = required_char()
    offset = optional_int()
    limit = optional_int()

class CenterGetTotalAttendanceCountOfCenterQuerySerializer(RequestSerializer):
    userId = required_int()
    date = required_char()

class CenterLogDtoSerializer(serializers.Serializer):
    centerId = serializers.IntegerField(required=True)
    status = serializers.BooleanField(allow_null=True, required=False)
    userId = serializers.IntegerField(allow_null=True, required=False)
    reason = serializers.CharField(allow_null=True, required=False)

class CenterGetCenteryIdQuerySerializer(RequestSerializer):
    centeId = required_int()


# CLASS serializers ------------------------------------------------------------------------------------------------------------------------------

# Class Serializers
class ClassDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    classEnrolmentId = serializers.CharField(allow_null=True, required=False)
    name = serializers.CharField(required=True)
    centerId = serializers.IntegerField(required=True)
    userId = serializers.IntegerField(required=True)
    totalStudents = serializers.IntegerField(required=True)
    avilableStudents = serializers.IntegerField(required=True)

class CancelClassDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
    reason = serializers.CharField(required=True)
    cancelBy = serializers.IntegerField(required=True)

class EndClassDtoSerializer(serializers.Serializer):
    Id = serializers.IntegerField(required=True)

class UpdateClassSubStatusDtoSerializer(serializers.Serializer):
    Id = serializers.IntegerField(required=True)

class ClassCancelTeacherDtoSerializer(serializers.Serializer):
    Id = serializers.IntegerField(required=False)
    CenterId = serializers.IntegerField(required=True)
    StartingDate = serializers.DateTimeField(required=True)
    EndingDate = serializers.DateTimeField(required=True)
    CreatedOn = serializers.DateTimeField(allow_null=True, required=False)
    UsersId = serializers.IntegerField(required=True)
    Reason = serializers.CharField(allow_null=True, required=False)

class ClassLiveDetailDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True, required=False)
    status = serializers.IntegerField(allow_null=True, required=False)
    startDate = serializers.DateTimeField(allow_null=True, required=False)
    endDate = serializers.DateTimeField(allow_null=True, required=False)
    totalStudents = serializers.IntegerField(allow_null=True, required=False)
    avilableStudents = serializers.IntegerField(allow_null=True, required=False)
    subStatus = serializers.IntegerField(allow_null=True, required=False)

class ClassGetClassCurrentStatusQuerySerializer(RequestSerializer):
    centerId = required_int()
    teacherId = required_int()

class ClassGetLiveClassDetailQuerySerializer(RequestSerializer):
    classId = required_int()

class ClassDeleteClassByTeacherIdQuerySerializer(RequestSerializer):
    classId = required_int()

class ClassSaveClassRequestSerializer(RequestSerializer):
    Id = optional_int()
    ClassEnrolmentId = optional_char()
    Name = required_char()
    CenterId = required_int()
    UserId = required_int()
    TotalStudents = required_int()
    AvilableStudents = required_int()


# DASHBOARD serializers ------------------------------------------------------------------------------------------------------------------------------
class DashboardCenterDateRangeQuerySerializer(RequestSerializer):
    foreign_key_fields = {"centerId": Center}
    centerId = optional_int()
    startDate = optional_datetime()
    endDate = optional_datetime()

    
class DashboardGetCenterDetailByMonthQuerySerializer(RequestSerializer):
    foreign_key_fields = {"centerId": Center}
    centerId = optional_int()
    month = optional_int()
    year = optional_int()

    
class DashboardFilterQuerySerializer(RequestSerializer):
    foreign_key_fields = {
        "districtId": District,
        "vidhanSabhaId": VidhanSabha,
        "panchaytaId": Panchayat,
        "villageId": Village,
    }

    districtId = optional_int()
    vidhanSabhaId = optional_int()
    panchaytaId = optional_int()
    villageId = optional_int()
    startDate = optional_datetime()
    endDate = optional_datetime()

class DashboardDistrictOfCenterByFilterQuerySerializer(RequestSerializer):
    districtId = optional_int()
    vidhanSabhaId = optional_int()
    startDate = optional_datetime()
    endDate = optional_datetime()



# District Serializers ---------------------------------------------------------------------------------------------------------------------
class DistrictSaveDistrictRequestSerializer(RequestSerializer):
    Id = optional_int()
    DistrictGuidId = optional_char()
    Name = required_char()
    Status = optional_bool()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()

class DistrictDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    districtGuidId = serializers.CharField(source='DistrictGuidId', allow_null=True, required=False)
    name = serializers.CharField(source='Name', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    createdOn = serializers.DateTimeField(source='CreatedOn', allow_null=True, required=False)
    createdBy = serializers.IntegerField(source='CreatedBy', allow_null=True, required=False)

class PaginationQuerySerializer(RequestSerializer):
    offset = optional_int()
    limit = optional_int()


class FileSendNotificationRequestSerializer(RequestSerializer):
    userId = optional_int()
    DeviceId = optional_char()
    ListOfDeviceIds = serializers.ListField(child=serializers.CharField(), required=False)
    IsAndroiodDevice = optional_bool()
    Title = optional_char()
    Body = optional_char()


class FileUploadProfileImageRequestSerializer(RequestSerializer):
    files = serializers.ListField(child=serializers.FileField(), required=False)


# Holidays Serializers
class HolidaysSaveHolidaysRequestSerializer(RequestSerializer):
    # Remove foreign_key_list_fields for ListCenterIds
    Id = optional_int()
    Name = required_char()
    Description = optional_char()
    Status = optional_bool()
    StartDate = required_datetime()
    EndDate = optional_datetime()
    CreatedBy = required_int()
    CreatedOn = optional_datetime()
    ListCenterIds = serializers.CharField(required=True, allow_blank=False)

    def validate_ListCenterIds(self, value):
        """Validate that ListCenterIds contains valid integers and centers exist"""
        if not value or not value.strip():
            raise serializers.ValidationError("ListCenterIds cannot be empty")
        
        # Split and get IDs
        ids = [x.strip() for x in value.split(',') if x.strip()]
        if not ids:
            raise serializers.ValidationError("ListCenterIds must contain at least one valid ID")
        
        # Validate each ID is an integer
        try:
            center_ids = [int(x) for x in ids]
        except ValueError:
            raise serializers.ValidationError("ListCenterIds must contain valid integer IDs separated by commas")
        
        # Check if centers exist
        existing_centers = Center.objects.filter(id__in=center_ids).values_list('id', flat=True)
        missing_ids = [str(cid) for cid in center_ids if cid not in existing_centers]
        if missing_ids:
            raise serializers.ValidationError(f"Center ids do not exist: {missing_ids}")
        
        return value

class HolidaysTeacherIdQuerySerializer(RequestSerializer):
    teacherId = required_int()

class HolidaysCenterIdQuerySerializer(RequestSerializer):
    centerId = required_int()

class HolidaysYearQuerySerializer(RequestSerializer):
    year = required_int()

class HolidaysGetAllHolidaysQuerySerializer(RequestSerializer):
    status = optional_int()
    userId = optional_int()



class HolidaysDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    name = serializers.CharField(source='Name', allow_null=True, required=False)
    description = serializers.CharField(source='Description', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    startDate = serializers.DateTimeField(source='StartDate', allow_null=True, required=False)
    endDate = serializers.DateTimeField(source='EndDate', allow_null=True, required=False)
    createdBy = serializers.IntegerField(source='CreatedBy', allow_null=True, required=False)
    createdOn = serializers.DateTimeField(source='CreatedOn', allow_null=True, required=False)
    centerId = serializers.IntegerField(source='CenterId', allow_null=True, required=False)
    centerName = serializers.CharField(source='CenterName', allow_null=True, required=False)

# Panchayat Serializers -----------------------------------------------------------------------------------------------
class PanchayatSavePanchayatRequestSerializer(RequestSerializer):
    foreign_key_fields = {"DistrictId": District, "VidhanSabhaId": VidhanSabha}
    
    Id = optional_int()
    PanchayatGuidId = optional_char()
    Name = required_char()
    Status = optional_bool()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()
    DistrictId = required_int()
    VidhanSabhaId = required_int()

class PanchayatByDistrictAndVidhanSabhaQuerySerializer(RequestSerializer):
    districtId = required_int()
    vidhanSabhaId = required_int()

class PanchayatDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    panchayatGuidId = serializers.CharField(source='PanchayatGuidId', allow_null=True, required=False)
    name = serializers.CharField(source='Name', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    createdOn = serializers.DateTimeField(source='CreatedOn', allow_null=True, required=False)
    createdBy = serializers.IntegerField(source='CreatedBy', allow_null=True, required=False)
    districtId = serializers.IntegerField(source='DistrictId')
    vidhanSabhaId = serializers.IntegerField(source='VidhanSabhaId')
    districtName = serializers.CharField(source='DistrictName', allow_null=True, required=False)
    vidhanSabhaName = serializers.CharField(source='VidhanSabhaName', allow_null=True, required=False)
    village = serializers.ListField(allow_null=True, required=False)

class NameCheckQuerySerializer(RequestSerializer):
    name = required_char()


class NameCheckQuerySerializer(RequestSerializer):
    name = required_char()


# Student Serializers
class StudentSaveStudentRequestSerializer(RequestSerializer):
    foreign_key_fields = {
        "VidhanSabhaId": VidhanSabha,
        "DistrictId": District,
        "PanchayatId": Panchayat,
        "CenterId": Center,
        "VillageId": Village,
        "SchoolId": School,
    }
    
    Id = serializers.IntegerField(required=False, allow_null=True)
    EnrollmentId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    FullName = serializers.CharField(required=True)
    MotherName = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    FatherName = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Age = serializers.IntegerField(required=False, allow_null=True)
    Gender = serializers.CharField(required=True)
    Contact = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    DateOfBirth = serializers.CharField(required=True)
    Email = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Remarks = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Grade = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    PhoneNumber = serializers.CharField(required=True)
    ProfileImage = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    WhatsApp = serializers.CharField(required=True)
    FullAddress = serializers.CharField(required=True)
    JoiningDate = serializers.DateTimeField(required=False, allow_null=True)
    CreatedOn = serializers.DateTimeField(required=False, allow_null=True)
    VidhanSabhaId = serializers.IntegerField(required=True)
    DistrictId = serializers.IntegerField(required=True)
    PanchayatId = serializers.IntegerField(required=True)
    CenterId = serializers.IntegerField(required=True)
    CreatedBy = serializers.IntegerField(required=True)
    VillageId = serializers.IntegerField(required=False, allow_null=True)
    Education = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    FatherMobileNumber = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    FatherOccupation = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    MotherMobileNumber = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    MotherOccupation = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Category = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Bpl = serializers.BooleanField(required=False, allow_null=True)
    SchoolId = serializers.IntegerField(required=True)
    #SchoolName = serializers.CharField(required=False, allow_null=True, allow_blank=True)

class StudentGetStudentByIdQuerySerializer(RequestSerializer):
    studentId = required_int()

class StudentUpdateStudentActiveOrInactiveRequestSerializer(RequestSerializer):
    Id = required_int()
    Status = required_int()

class StudentGetTotalStudentPresentQuerySerializer(RequestSerializer):
    scanDate = required_datetime()
    userId = required_int()

class StudentGetAllStudentsQuerySerializer(RequestSerializer):
    userId = required_int()
    districtId = optional_int()
    vidhanSabhaId = optional_int()
    panchayatId = optional_int()
    villageId = optional_int()

class StudentDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    enrollmentId = serializers.CharField(source='EnrollmentId', allow_null=True, required=False)
    fullName = serializers.CharField(source='FullName', allow_null=True, required=False)
    motherName = serializers.CharField(source='MotherName', allow_null=True, required=False)
    fatherName = serializers.CharField(source='FatherName', allow_null=True, required=False)
    age = serializers.IntegerField(source='Age', allow_null=True, required=False)
    gender = serializers.CharField(source='Gender', allow_null=True, required=False)
    contact = serializers.CharField(source='Contact', allow_null=True, required=False)
    dateOfBirth = serializers.CharField(source='DateOfBirth', allow_null=True, required=False)
    email = serializers.CharField(source='Email', allow_null=True, required=False)
    remarks = serializers.CharField(source='Remarks', allow_null=True, required=False)
    grade = serializers.CharField(source='Grade', allow_null=True, required=False)
    phoneNumber = serializers.CharField(source='PhoneNumber', allow_null=True, required=False)
    profileImage = serializers.CharField(source='ProfileImage', allow_null=True, required=False)
    whatsApp = serializers.CharField(source='WhatsApp', allow_null=True, required=False)
    fullAddress = serializers.CharField(source='FullAddress', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    joiningDate = serializers.DateTimeField(source='JoiningDate', allow_null=True, required=False)
    centerName = serializers.CharField(source='CenterName', allow_null=True, required=False)
    teacherName = serializers.CharField(source='TeacherName', allow_null=True, required=False)
    centerId = serializers.IntegerField(source='CenterId')
    districtId = serializers.IntegerField(source='DistrictId')
    vidhanSabhaId = serializers.IntegerField(source='VidhanSabhaId')
    villageId = serializers.IntegerField(source='VillageId', allow_null=True, required=False)
    panchayatId = serializers.IntegerField(source='PanchayatId')
    fatherMobileNumber = serializers.CharField(source='FatherMobileNumber', allow_null=True, required=False)
    fatherOccupation = serializers.CharField(source='FatherOccupation', allow_null=True, required=False)
    motherMobileNumber = serializers.CharField(source='MotherMobileNumber', allow_null=True, required=False)
    motherOccupation = serializers.CharField(source='MotherOccupation', allow_null=True, required=False)
    category = serializers.CharField(source='Category', allow_null=True, required=False)
    bpl = serializers.BooleanField(source='Bpl', allow_null=True, required=False)
    schoolId = serializers.IntegerField(source='SchoolId', allow_null=True, required=False)
    schoolName = serializers.CharField(source='SchoolName', allow_null=True, required=False)

class StudentDetailDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    enrollmentId = serializers.CharField(source='EnrollmentId', allow_null=True, required=False)
    fullName = serializers.CharField(source='FullName', allow_null=True, required=False)
    motherName = serializers.CharField(source='MotherName', allow_null=True, required=False)
    fatherName = serializers.CharField(source='FatherName', allow_null=True, required=False)
    age = serializers.IntegerField(source='Age', allow_null=True, required=False)
    gender = serializers.CharField(source='Gender', allow_null=True, required=False)
    contact = serializers.CharField(source='Contact', allow_null=True, required=False)
    dateOfBirth = serializers.CharField(source='DateOfBirth', allow_null=True, required=False)
    email = serializers.CharField(source='Email', allow_null=True, required=False)
    remarks = serializers.CharField(source='Remarks', allow_null=True, required=False)
    grade = serializers.CharField(source='Grade', allow_null=True, required=False)
    phoneNumber = serializers.CharField(source='PhoneNumber', allow_null=True, required=False)
    profileImage = serializers.CharField(source='ProfileImage', allow_null=True, required=False)
    whatsApp = serializers.CharField(source='WhatsApp', allow_null=True, required=False)
    fullAddress = serializers.CharField(source='FullAddress', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    joiningDate = serializers.DateTimeField(source='JoiningDate', allow_null=True, required=False)
    centerName = serializers.CharField(source='CenterName', allow_null=True, required=False)
    teacherName = serializers.CharField(source='TeacherName', allow_null=True, required=False)
    centerId = serializers.IntegerField(source='CenterId')
    districtId = serializers.IntegerField(source='DistrictId')
    vidhanSabhaId = serializers.IntegerField(source='VidhanSabhaId')
    villageId = serializers.IntegerField(source='VillageId', allow_null=True, required=False)
    panchayatId = serializers.IntegerField(source='PanchayatId')
    fatherMobileNumber = serializers.CharField(source='FatherMobileNumber', allow_null=True, required=False)
    fatherOccupation = serializers.CharField(source='FatherOccupation', allow_null=True, required=False)
    motherMobileNumber = serializers.CharField(source='MotherMobileNumber', allow_null=True, required=False)
    motherOccupation = serializers.CharField(source='MotherOccupation', allow_null=True, required=False)
    category = serializers.CharField(source='Category', allow_null=True, required=False)
    bpl = serializers.BooleanField(source='Bpl', allow_null=True, required=False)
    schoolId = serializers.IntegerField(source='SchoolId', allow_null=True, required=False)
    schoolName = serializers.CharField(source='SchoolName', allow_null=True, required=False)

class StudentActiveDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
    status = serializers.IntegerField(required=True)

class StudentPresentClassDtoSerializer(serializers.Serializer):
    totalStudents = serializers.IntegerField(allow_null=True, required=False)
    presentStudents = serializers.IntegerField(allow_null=True, required=False)
    totalClasses = serializers.IntegerField(allow_null=True, required=False)
    totalActiveClasses = serializers.IntegerField(allow_null=True, required=False)
    completedClassCount = serializers.IntegerField(allow_null=True, required=False)
    upComingClassCount = serializers.IntegerField(allow_null=True, required=False)
    cancelClassCount = serializers.IntegerField(allow_null=True, required=False)
    
# StudentAttendance Serializers
class StudentAttendanceSaveRequestSerializer(RequestSerializer):
    foreign_key_fields = {"ClassId": ClassModel, "CenterId": Center}
    # foreign_key_list_fields removed - StudentIds is now a comma-separated string
    
    Id = optional_int()
    ClassId = required_int()
    UserId = required_int()
    StudentIds = required_char()  # Comma-separated string (matches .NET API)
    ScanDate = required_datetime()
    CenterId = required_int()

class StudentAttendanceCenterQuerySerializer(RequestSerializer):
    centerId = required_int()

class StudentAttendanceStatusQuerySerializer(StudentAttendanceCenterQuerySerializer):
    scanDate = required_char()

class StudentAttendanceByMonthQuerySerializer(StudentAttendanceCenterQuerySerializer):
    studentId = required_int()
    month = required_int()
    year = required_int()

    
# School Serializers
class SchoolSaveSchoolRequestSerializer(RequestSerializer):
    Id = optional_int()
    SchoolName = required_char()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()

class SchoolDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    schoolName = serializers.CharField(source='SchoolName', allow_null=True, required=False)
    createdOn = serializers.DateTimeField(source='CreatedOn', allow_null=True, required=False)
    createdBy = serializers.IntegerField(source='CreatedBy', allow_null=True, required=False)


class UserSaveSuperAdminRequestSerializer(RequestSerializer):
    Id = optional_int()
    EnrolmentRollId = optional_char()
    Name = required_char()
    Password = required_char()
    Token = optional_char()
    Email = optional_char()
    Type = required_int()
    Age = optional_int()
    Gender = required_char()
    Contact = optional_char()
    Status = optional_bool()
    DateOfBirth = required_char()
    PhoneNumber = required_char()
    Picture = serializers.ImageField(required=False, allow_null=True)
    WhatsApp = optional_char()
    LastLoginTime = optional_char()
    FullAddress = optional_char()
    RoleId = optional_int()
    CreatedOn = optional_datetime()
    EnrollmentDate = optional_datetime()
    CreatedBy = required_int()


class UserUpdateDeviceIdRequestSerializer(RequestSerializer):
    foreign_key_fields = {"userId": User}
    userId = required_int()
    DeviceId = required_char()


class UserSaveSuperAdminRequestSerializer(RequestSerializer):
    Id = serializers.IntegerField(required=False, allow_null=True)
    EnrolmentRollId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Name = serializers.CharField(required=True)
    Password = serializers.CharField(required=True)
    Token = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Email = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Type = serializers.IntegerField(required=True)
    Age = serializers.IntegerField(required=False, allow_null=True)
    Gender = serializers.CharField(required=True)
    Contact = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Status = serializers.BooleanField(required=False, allow_null=True)
    DateOfBirth = serializers.CharField(required=True)
    PhoneNumber = serializers.CharField(required=True)
    Picture = serializers.ImageField(required=False, allow_null=True)
    WhatsApp = serializers.CharField(required=True)
    LastLoginTime = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    FullAddress = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    # RoleId = serializers.IntegerField(required=False, allow_null=True,)
    CreatedOn = serializers.DateTimeField(required=False, allow_null=True)
    EnrollmentDate = serializers.DateTimeField(required=False, allow_null=True) 
    CreatedBy = serializers.IntegerField(required=True)


class UserSaveUserRequestSerializer(UserSaveSuperAdminRequestSerializer):
    foreign_key_fields = {
        "VidhanSabhaId": VidhanSabha,
        "DistrictId": District,
        "VillageId": Village,
    }
    
    DeviceId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Education = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    VidhanSabhaId = serializers.IntegerField(required=False, allow_null=True)
    DistrictId = serializers.IntegerField(required=False, allow_null=True)
    VillageId = serializers.IntegerField(required=False, allow_null=True)
    PanchayatId = serializers.IntegerField(required=False, allow_null=True)
    AssignedTeacherStatus = serializers.BooleanField(required=False, allow_null=True)
    AssignedRegionalAdminStatus = serializers.BooleanField(required=False, allow_null=True)
    GuardianName = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    GuardianNumber = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ListOfPanchayatIds = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        
        # RegionalAdmin (Type=2) requires ListOfPanchayatIds
        if attrs.get('Type') == 2:
            list_of_panchayat_ids = attrs.get('ListOfPanchayatIds')
            if not list_of_panchayat_ids:
                raise serializers.ValidationError({
                    "ListOfPanchayatIds": "ListOfPanchayatIds is required for Regional Admin"
                })
            
            # Parse and validate panchayat IDs
            if isinstance(list_of_panchayat_ids, str):
                panchayat_ids = [int(x.strip()) for x in list_of_panchayat_ids.split(',') if x.strip()]
            else:
                panchayat_ids = list_of_panchayat_ids if isinstance(list_of_panchayat_ids, list) else []
            
            # Validate panchayat IDs exist
            existing_ids = set(Panchayat.objects.filter(pk__in=panchayat_ids).values_list("id", flat=True))
            missing_ids = [pid for pid in panchayat_ids if pid not in existing_ids]
            if missing_ids:
                raise serializers.ValidationError({
                    "ListOfPanchayatIds": f"Panchayat ids do not exist: {missing_ids}"
                })
        
        return attrs
    

class UserGetUserByIdQuerySerializer(RequestSerializer):
    foreign_key_fields = {"userId": User}
    userId = required_int()


class UserGetUserDetailByPhoneNumberQuerySerializer(RequestSerializer):
    phoneNumer = required_char()


class UserUpdatePasswordQuerySerializer(RequestSerializer):
    foreign_key_fields = {"userId": User}
    userId = required_int()
    newPassword = required_char()


class UserGetAllTeachersQuerySerializer(serializers.Serializer):
    userId = serializers.IntegerField(required=False, default=0)


# User serializers
class LoginSerializer(serializers.Serializer):
    mobileNumber = serializers.CharField(max_length=15, required=False, allow_blank=False)
    mobile_number = serializers.CharField(max_length=15, required=False, allow_blank=False, write_only=True)
    password = serializers.CharField(required=True, allow_blank=False, trim_whitespace=False)

    def validate(self, attrs):
        mobile_number = attrs.get("mobileNumber") or attrs.get("mobile_number")
        if not mobile_number:
            raise serializers.ValidationError({"mobileNumber": "Mobile number is required."})
        attrs["mobileNumber"] = mobile_number

        if not attrs.get("password"):
            raise serializers.ValidationError({"password": "Password is required."})

        return attrs
    
# serializers.py - Add/Update these serializers

class UserLoginResponseSerializer(serializers.Serializer):
    """Matches .NET LoginUser response exactly"""
    id = serializers.IntegerField()
    enrolmentRollId = serializers.CharField(allow_null=True)
    password = serializers.SerializerMethodField()
    name = serializers.CharField(allow_null=True)
    token = serializers.CharField(allow_null=True)
    deviceId = serializers.CharField(allow_null=True)
    type = serializers.IntegerField(allow_null=True)
    age = serializers.IntegerField(allow_null=True)
    gender = serializers.CharField(allow_null=True)
    contact = serializers.CharField(allow_null=True)
    status = serializers.BooleanField(allow_null=True)
    dateOfBirth = serializers.CharField(allow_null=True)
    email = serializers.CharField(allow_null=True)
    phoneNumber = serializers.CharField(allow_null=True)
    picture = serializers.CharField(allow_null=True)
    whatsApp = serializers.CharField(allow_null=True)
    lastLoginTime = serializers.CharField(allow_null=True)
    fullAddress = serializers.CharField(allow_null=True)
    roleId = serializers.IntegerField(allow_null=True)
    createdOn = serializers.SerializerMethodField()
    enrollmentDate = serializers.SerializerMethodField()
    guardianName = serializers.CharField(allow_null=True)
    guardianNumber = serializers.CharField(allow_null=True)
    education = serializers.CharField(allow_null=True)
    createdBy = serializers.IntegerField(allow_null=True)
    vidhanSabhaId = serializers.IntegerField(allow_null=True)
    districtId = serializers.IntegerField(allow_null=True)
    villageId = serializers.IntegerField(allow_null=True)
    panchayatId = serializers.IntegerField(allow_null=True)
    assignedTeacherStatus = serializers.BooleanField(allow_null=True)
    assignedRegionalAdminStatus = serializers.BooleanField(allow_null=True)
    listOfPanchayatId = serializers.ListField(child=serializers.IntegerField(), allow_null=True)
    district = serializers.DictField(allow_null=True)
    vidhanSabha = serializers.DictField(allow_null=True)
    panchayat = serializers.DictField(allow_null=True)
    village = serializers.DictField(allow_null=True)
    regionalAdminPanchayat = serializers.ListField(child=serializers.DictField(), allow_null=True)
    center = serializers.DictField(allow_null=True)
    centers = serializers.ListField(child=serializers.DictField(), allow_null=True)
    centerAssignUser = serializers.DictField(allow_null=True)

    def get_password(self, obj):
        return None

    def get_token(self, obj):
        return obj.get('token')

    def get_createdOn(self, obj):
        value = obj.get('createdOn') or obj.get('created_on')
        return format_dotnet_datetime(value)

    def get_enrollmentDate(self, obj):
        value = obj.get('enrollmentDate') or obj.get('enrollment_date')
        return format_dotnet_datetime(value)


class UserDeviceDtoSerializer(serializers.Serializer):
    userId = serializers.IntegerField(required=True)
    DeviceId = serializers.CharField(required=True)

class UserUpdatePasswordQuerySerializer(RequestSerializer):
    userId = required_int()
    newPassword = required_char()

class UserSearchDataQuerySerializer(RequestSerializer):
    type = optional_char()
    queryString = optional_char()

class SuperAdminDtoSerializer(serializers.Serializer):
    Id = serializers.IntegerField(required=False, allow_null=True)
    EnrolmentRollId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Name = serializers.CharField(required=True)
    Password = serializers.CharField(required=True)
    Token = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Email = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Type = serializers.IntegerField(required=True)
    Age = serializers.IntegerField(required=False, allow_null=True)
    Gender = serializers.CharField(required=True)
    Contact = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Status = serializers.BooleanField(required=False, allow_null=True)
    DateOfBirth = serializers.CharField(required=True)
    PhoneNumber = serializers.CharField(required=True)
    Picture = serializers.ImageField(required=False, allow_null=True)
    WhatsApp = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    LastLoginTime = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    FullAddress = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    RoleId = serializers.IntegerField(required=False, allow_null=True)
    CreatedOn = serializers.DateTimeField(required=False, allow_null=True)
    EnrollmentDate = serializers.DateTimeField(required=False, allow_null=True)
    CreatedBy = serializers.IntegerField(required=False, allow_null=True)

class UserDtoSerializer(SuperAdminDtoSerializer):
    deviceId = serializers.CharField(allow_null=True, required=False)
    education = serializers.CharField(allow_null=True, required=False)
    vidhanSabhaId = serializers.IntegerField(allow_null=True, required=False)
    districtId = serializers.IntegerField(allow_null=True, required=False)
    villageId = serializers.IntegerField(allow_null=True, required=False)
    panchayatId = serializers.IntegerField(allow_null=True, required=False)
    assignedTeacherStatus = serializers.BooleanField(allow_null=True, required=False)
    assignedRegionalAdminStatus = serializers.BooleanField(allow_null=True, required=False)
    guardianName = serializers.CharField(allow_null=True, required=False)
    guardianNumber = serializers.CharField(allow_null=True, required=False)
    listOfPanchayatIds = serializers.CharField(allow_null=True, required=False)


class VidhanSabhaSaveVidhanSabhaRequestSerializer(RequestSerializer):
    foreign_key_fields = {"DistrictId": District}

    Id = optional_int()
    VidhanSabhaGuidId = optional_char()
    Name = required_char()
    Status = optional_bool()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()
    DistrictId = required_int()


class VidhanSabhaByDistrictIdQuerySerializer(RequestSerializer):
    foreign_key_fields = {"districtId": District}
    districtId = required_int()
    
# VidhanSabha Serializers
class VidhanSabhaSaveVidhanSabhaRequestSerializer(RequestSerializer):
    foreign_key_fields = {"DistrictId": District}
    
    Id = optional_int()
    VidhanSabhaGuidId = optional_char()
    Name = required_char()
    Status = optional_bool()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()
    DistrictId = required_int()


class VidhanSabhaDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    vidhanSabhaGuidId = serializers.CharField(source='VidhanSabhaGuidId', allow_null=True, required=False)
    name = serializers.CharField(source='Name', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    createdOn = serializers.DateTimeField(source='CreatedOn', allow_null=True, required=False)
    createdBy = serializers.IntegerField(source='CreatedBy', allow_null=True, required=False)
    districtId = serializers.IntegerField(source='DistrictId')
    districtName = serializers.CharField(source='DistrictName', allow_null=True, required=False)


# Village Serializers
class VillageSaveVillageRequestSerializer(RequestSerializer):
    foreign_key_fields = {
        "DistrictId": District,
        "VidhanSabhaId": VidhanSabha,
        "PanchayatId": Panchayat,
    }
    
    Id = optional_int()
    VillageGuidId = optional_char()
    Name = required_char()
    Status = optional_bool()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()
    DistrictId = required_int()
    VidhanSabhaId = required_int()
    PanchayatId = required_int()

class VillageByDistrictVidhanSabhaAndPanchayatQuerySerializer(RequestSerializer):
    districtId = required_int()
    vidhanSabhaId = required_int()
    panchayatId = required_int()

class VillageDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    villageGuidId = serializers.CharField(source='VillageGuidId', allow_null=True, required=False)
    name = serializers.CharField(source='Name', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    createdOn = serializers.DateTimeField(source='CreatedOn', allow_null=True, required=False)
    createdBy = serializers.IntegerField(source='CreatedBy', allow_null=True, required=False)
    districtId = serializers.IntegerField(source='DistrictId')
    vidhanSabhaId = serializers.IntegerField(source='VidhanSabhaId')
    panchayatId = serializers.IntegerField(source='PanchayatId')
    panchayatName = serializers.CharField(source='PanchayatName', allow_null=True, required=False)
    vidhanSabhaName = serializers.CharField(source='VidhanSabhaName', allow_null=True, required=False)
    districtName = serializers.CharField(source='DistrictName', allow_null=True, required=False)

# Teacher Serializers
class TeacherSaveTeacherRequestSerializer(RequestSerializer):
    foreign_key_fields = {
        "VidhanSabhaId": VidhanSabha,
        "DistrictId": District,
        "PanchayatId": Panchayat,
        "CenterId": Center,
        "VillageId": Village,
    }
    
    Id = optional_int()
    TeacherGuidId = optional_char()
    FullName = required_char()
    Age = optional_int()
    Gender = required_char()
    DateOfBirth = optional_char()
    PhoneNumber = required_char()
    WhatsApp = optional_char()
    Email = optional_char()
    Status = optional_bool()
    Count = optional_int()
    Picture = serializers.ImageField(required=False, allow_null=True)
    Password = required_char()
    FullAddress = optional_char()
    Education = optional_char()
    VidhanSabhaId = optional_int()
    DistrictId = optional_int()
    PanchayatId = optional_int()
    CenterId = optional_int()
    VillageId = optional_int()

class TeacherLoginRequestSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    

class TeacherUnAssignedDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True, required=False)
    assigned = serializers.BooleanField(allow_null=True, required=False)
    profile = serializers.CharField(allow_null=True, required=False)
    phoneNumber = serializers.CharField(allow_null=True, required=False)
    
class TeacherDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True, required=False)
    assigned = serializers.BooleanField(allow_null=True, required=False)
    profile = serializers.CharField(allow_null=True, required=False)
    phoneNumber = serializers.CharField(allow_null=True, required=False)

class TeacherDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    teacherGuidId = serializers.CharField(source='TeacherGuidId', allow_null=True, required=False)
    userId = serializers.IntegerField(source='UserId')
    name = serializers.CharField(source='user__name', allow_null=True, required=False)
    email = serializers.CharField(source='user__email', allow_null=True, required=False)
    phoneNumber = serializers.CharField(source='user__phone_number', allow_null=True, required=False)
    age = serializers.IntegerField(source='Age', allow_null=True, required=False)
    gender = serializers.CharField(source='Gender', allow_null=True, required=False)
    dateOfBirth = serializers.CharField(source='DateOfBirth', allow_null=True, required=False)
    contact = serializers.CharField(source='Contact', allow_null=True, required=False)
    fullAddress = serializers.CharField(source='FullAddress', allow_null=True, required=False)
    education = serializers.CharField(source='Education', allow_null=True, required=False)
    guardianName = serializers.CharField(source='GuardianName', allow_null=True, required=False)
    guardianNumber = serializers.CharField(source='GuardianNumber', allow_null=True, required=False)
    count = serializers.IntegerField(source='Count', allow_null=True, required=False)
    assignedTeacherStatus = serializers.BooleanField(source='AssignedTeacherStatus', allow_null=True, required=False)
    assignedRegionalAdminStatus = serializers.BooleanField(source='AssignedRegionalAdminStatus', allow_null=True, required=False)
    enrollmentDate = serializers.DateTimeField(source='EnrollmentDate', allow_null=True, required=False)
    districtId = serializers.IntegerField(source='DistrictId', allow_null=True, required=False)
    vidhanSabhaId = serializers.IntegerField(source='VidhanSabhaId', allow_null=True, required=False)
    panchayatId = serializers.IntegerField(source='PanchayatId', allow_null=True, required=False)
    villageId = serializers.IntegerField(source='VillageId', allow_null=True, required=False)
    centerId = serializers.IntegerField(source='CenterId', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    createdOn = serializers.DateTimeField(source='CreatedOn', allow_null=True, required=False)
    createdBy = serializers.IntegerField(source='CreatedBy', allow_null=True, required=False)
    districtName = serializers.CharField(source='district__name', allow_null=True, required=False)
    vidhanSabhaName = serializers.CharField(source='vidhan_sabha__name', allow_null=True, required=False)
    villageName = serializers.CharField(source='village__name', allow_null=True, required=False)
    panchayatName = serializers.CharField(source='panchayat__name', allow_null=True, required=False)
    centerName = serializers.CharField(source='center__center_name', allow_null=True, required=False)


class LoginRequestSerializer(LoginSerializer):
    pass


# RegionalAdmin Serializers
class RegionalAdminSaveRegionalAdminRequestSerializer(RequestSerializer):
    foreign_key_fields = {
        "VidhanSabhaId": VidhanSabha,
        "DistrictId": District,
        "PanchayatId": Panchayat,
        "CenterId": Center,
        "VillageId": Village,
    }
    
    Id = optional_int()
    RegionalAdminGuidId = optional_char()
    FullName = required_char()
    Age = optional_int()
    Gender = required_char()
    DateOfBirth = optional_char()
    PhoneNumber = required_char()
    WhatsApp = optional_char()
    Email = optional_char()
    Status = optional_bool()
    RoleId = optional_int()
    Picture = serializers.ImageField(required=False, allow_null=True)
    Password = required_char()
    FullAddress = optional_char()
    Education = optional_char()
    VidhanSabhaId = optional_int()
    DistrictId = optional_int()
    PanchayatId = optional_int()
    CenterId = optional_int()
    VillageId = optional_int()
    Type = optional_int()
    Contact = optional_char()

class RegionalAdminLoginRequestSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    
class RegionalAdminDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True, required=False)
    profile = serializers.CharField(allow_null=True, required=False)

class RegionalAdminDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='Id')
    regionalAdminGuidId = serializers.CharField(source='RegionalAdminGuidId', allow_null=True, required=False)
    userId = serializers.IntegerField(source='UserId')
    name = serializers.CharField(source='user__name', allow_null=True, required=False)
    email = serializers.CharField(source='user__email', allow_null=True, required=False)
    phoneNumber = serializers.CharField(source='user__phone_number', allow_null=True, required=False)
    age = serializers.IntegerField(source='Age', allow_null=True, required=False)
    gender = serializers.CharField(source='Gender', allow_null=True, required=False)
    dateOfBirth = serializers.CharField(source='DateOfBirth', allow_null=True, required=False)
    contact = serializers.CharField(source='Contact', allow_null=True, required=False)
    fullAddress = serializers.CharField(source='FullAddress', allow_null=True, required=False)
    education = serializers.CharField(source='Education', allow_null=True, required=False)
    guardianName = serializers.CharField(source='GuardianName', allow_null=True, required=False)
    guardianNumber = serializers.CharField(source='GuardianNumber', allow_null=True, required=False)
    assignedTeacherStatus = serializers.BooleanField(source='AssignedTeacherStatus', allow_null=True, required=False)
    assignedRegionalAdminStatus = serializers.BooleanField(source='AssignedRegionalAdminStatus', allow_null=True, required=False)
    enrollmentDate = serializers.DateTimeField(source='EnrollmentDate', allow_null=True, required=False)
    districtId = serializers.IntegerField(source='DistrictId', allow_null=True, required=False)
    vidhanSabhaId = serializers.IntegerField(source='VidhanSabhaId', allow_null=True, required=False)
    panchayatId = serializers.IntegerField(source='PanchayatId', allow_null=True, required=False)
    villageId = serializers.IntegerField(source='VillageId', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    createdOn = serializers.DateTimeField(source='CreatedOn', allow_null=True, required=False)
    createdBy = serializers.IntegerField(source='CreatedBy', allow_null=True, required=False)
    districtName = serializers.CharField(source='district__name', allow_null=True, required=False)
    vidhanSabhaName = serializers.CharField(source='vidhan_sabha__name', allow_null=True, required=False)
    villageName = serializers.CharField(source='village__name', allow_null=True, required=False)
    panchayatName = serializers.CharField(source='panchayat__name', allow_null=True, required=False)