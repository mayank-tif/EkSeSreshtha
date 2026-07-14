from datetime import datetime

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers
from .models import (
    Center,
    ClassModel,
    District,
    Holidays,
    Panchayat,
    RegionalAdmin,
    School,
    Student,
    Teacher,
    User,
    VidhanSabha,
    Village,
)
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
        "AssignedTeachers": Teacher,
        "AssignedRegionalAdmin": RegionalAdmin,
        "VidhanSabhaId": VidhanSabha,
        "DistrictId": District,
        "PanchayatId": Panchayat,
        "VillageId": Village,
    }

    Id = optional_int()
    CenterGuidId = optional_char()
    CenterName = required_char()
    AssignedTeachers = required_int()
    AssignedRegionalAdmin = required_int()
    StartedDate = optional_datetime()
    VidhanSabhaId = required_int()
    DistrictId = required_int()
    PanchayatId = required_int()
    VillageId = optional_int()



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
    teacher = serializers.DictField(source='teacher', allow_null=True, required=False)

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
    id = serializers.IntegerField(required=True)

class UpdateClassSubStatusDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)

class ClassCancelTeacherDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    centerId = serializers.IntegerField(required=True)
    startingDate = serializers.DateTimeField(required=True)
    endingDate = serializers.DateTimeField(required=True)
    createdOn = serializers.DateTimeField(allow_null=True, required=False)
    usersId = serializers.IntegerField(required=True)
    reason = serializers.CharField(allow_null=True, required=False)

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
    foreign_key_list_fields = {"ListCenterIds": Center}
    
    Id = optional_int()
    Name = required_char()
    Description = optional_char()
    Status = optional_bool()
    StartDate = required_datetime()
    EndDate = optional_datetime()
    CreatedBy = required_int()
    CreatedOn = optional_datetime()
    ListCenterIds = serializers.ListField(child=serializers.IntegerField(), required=True, allow_empty=False)

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
    
    Id = optional_int()
    EnrollmentId = optional_char()
    FullName = required_char()
    MotherName = optional_char()
    FatherName = optional_char()
    Age = optional_int()
    Gender = required_char()
    Contact = optional_char()
    DateOfBirth = required_char()
    Email = optional_char()
    Remarks = optional_char()
    Grade = optional_char()
    PhoneNumber = required_char()
    ProfileImage = optional_char()
    WhatsApp = required_char()
    FullAddress = required_char()
    JoiningDate = optional_datetime()
    CreatedOn = optional_datetime()
    VidhanSabhaId = required_int()
    DistrictId = required_int()
    PanchayatId = required_int()
    CenterId = required_int()
    CreatedBy = required_int()
    VillageId = optional_int()
    Education = optional_char()
    FatherMobileNumber = optional_char()
    FatherOccupation = optional_char()
    MotherMobileNumber = optional_char()
    MotherOccupation = optional_char()
    Category = optional_char()
    Bpl = optional_bool()
    SchoolId = required_int()
    SchoolName = optional_char()

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
    foreign_key_list_fields = {"StudentIds": Student}
    
    Id = optional_int()
    ClassId = required_int()
    UserId = required_int()
    StudentIds = serializers.ListField(child=serializers.IntegerField(), required=True, allow_empty=False)
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
    Picture = optional_char()
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
    Picture = serializers.CharField(required=False, allow_null=True, allow_blank=True)
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
    
class UserLoginResponseSerializer(serializers.ModelSerializer):
    enrolmentRollId = serializers.CharField(source="enrolment_roll_id", allow_null=True)
    password = serializers.SerializerMethodField()
    token = serializers.SerializerMethodField()
    deviceId = serializers.CharField(source="device_id", allow_null=True)
    dateOfBirth = serializers.CharField(source="date_of_birth", allow_null=True)
    phoneNumber = serializers.CharField(source="phone_number", allow_null=True)
    whatsApp = serializers.CharField(source="whats_app", allow_null=True)
    lastLoginTime = serializers.CharField(source="last_login_time", allow_null=True)
    fullAddress = serializers.CharField(source="full_address", allow_null=True)
    roleId = serializers.IntegerField(source="role_id", allow_null=True)
    createdOn = serializers.SerializerMethodField()
    enrollmentDate = serializers.SerializerMethodField()
    guardianName = serializers.CharField(source="guardian_name", allow_null=True)
    guardianNumber = serializers.CharField(source="guardian_number", allow_null=True)
    createdBy = serializers.IntegerField(source="created_by", allow_null=True)
    vidhanSabhaId = serializers.IntegerField(source="vidhan_sabha_id", allow_null=True)
    districtId = serializers.IntegerField(source="district_id", allow_null=True)
    villageId = serializers.IntegerField(source="village_id", allow_null=True)
    panchayatId = serializers.IntegerField(source="panchayat_id", allow_null=True)
    assignedTeacherStatus = serializers.BooleanField(source="assigned_teacher_status", allow_null=True)
    assignedRegionalAdminStatus = serializers.BooleanField(source="assigned_regional_admin_status", allow_null=True)
    listOfPanchayatId = serializers.SerializerMethodField()
    district = serializers.SerializerMethodField()
    vidhanSabha = serializers.SerializerMethodField()
    panchayat = serializers.SerializerMethodField()
    village = serializers.SerializerMethodField()
    regionalAdminPanchayat = serializers.SerializerMethodField()
    center = serializers.SerializerMethodField()
    centers = serializers.SerializerMethodField()
    centerAssignUser = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "enrolmentRollId",
            "password",
            "name",
            "token",
            "deviceId",
            "type",
            "age",
            "gender",
            "contact",
            "status",
            "dateOfBirth",
            "email",
            "phoneNumber",
            "picture",
            "whatsApp",
            "lastLoginTime",
            "fullAddress",
            "roleId",
            "createdOn",
            "enrollmentDate",
            "guardianName",
            "guardianNumber",
            "education",
            "createdBy",
            "vidhanSabhaId",
            "districtId",
            "villageId",
            "panchayatId",
            "assignedTeacherStatus",
            "assignedRegionalAdminStatus",
            "listOfPanchayatId",
            "district",
            "vidhanSabha",
            "panchayat",
            "village",
            "regionalAdminPanchayat",
            "center",
            "centers",
            "centerAssignUser",
        )

    def get_password(self, obj):
        return None

    def get_token(self, obj):
        return self.context.get("token") or obj.token

    def get_createdOn(self, obj):
        return format_dotnet_datetime(obj.created_on)

    def get_enrollmentDate(self, obj):
        return format_dotnet_datetime(obj.enrollment_date)

    def get_listOfPanchayatId(self, obj):
        return None

    def get_district(self, obj):
        return None

    def get_vidhanSabha(self, obj):
        return None

    def get_panchayat(self, obj):
        return None

    def get_village(self, obj):
        return None

    def get_regionalAdminPanchayat(self, obj):
        return None

    def get_center(self, obj):
        return None

    def get_centers(self, obj):
        return None

    def get_centerAssignUser(self, obj):
        return None


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
    id = serializers.IntegerField(required=False)
    enrolmentRollId = serializers.CharField(allow_null=True, required=False)
    name = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    token = serializers.CharField(allow_null=True, required=False)
    email = serializers.CharField(allow_null=True, required=False)
    type = serializers.IntegerField(required=True)
    age = serializers.IntegerField(allow_null=True, required=False)
    gender = serializers.CharField(required=True)
    contact = serializers.CharField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    dateOfBirth = serializers.CharField(required=True)
    phoneNumber = serializers.CharField(required=True)
    picture = serializers.CharField(allow_null=True, required=False)
    whatsApp = serializers.CharField(allow_null=True, required=False)
    lastLoginTime = serializers.CharField(allow_null=True, required=False)
    fullAddress = serializers.CharField(allow_null=True, required=False)
    roleId = serializers.IntegerField(allow_null=True, required=False)
    createdOn = serializers.DateTimeField(allow_null=True, required=False)
    enrollmentDate = serializers.DateTimeField(allow_null=True, required=False)
    createdBy = serializers.IntegerField(required=True)

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
    Picture = optional_char()
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
    fullName = serializers.CharField(source='FullName', allow_null=True, required=False)
    age = serializers.IntegerField(source='Age', allow_null=True, required=False)
    gender = serializers.CharField(source='Gender', allow_null=True, required=False)
    dateOfBirth = serializers.CharField(source='DateOfBirth', allow_null=True, required=False)
    phoneNumber = serializers.CharField(source='PhoneNumber', allow_null=True, required=False)
    whatsApp = serializers.CharField(source='WhatsApp', allow_null=True, required=False)
    email = serializers.CharField(source='Email', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    count = serializers.IntegerField(source='Count', allow_null=True, required=False)
    picture = serializers.CharField(source='Picture', allow_null=True, required=False)
    password = serializers.CharField(source='Password', allow_null=True, required=False)
    fullAddress = serializers.CharField(source='FullAddress', allow_null=True, required=False)
    education = serializers.CharField(source='Education', allow_null=True, required=False)
    token = serializers.CharField(source='Token', allow_null=True, required=False)


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
    Picture = optional_char()
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
    fullName = serializers.CharField(source='FullName', allow_null=True, required=False)
    age = serializers.IntegerField(source='Age', allow_null=True, required=False)
    gender = serializers.CharField(source='Gender', allow_null=True, required=False)
    dateOfBirth = serializers.CharField(source='DateOfBirth', allow_null=True, required=False)
    phoneNumber = serializers.CharField(source='PhoneNumber', allow_null=True, required=False)
    whatsApp = serializers.CharField(source='WhatsApp', allow_null=True, required=False)
    email = serializers.CharField(source='Email', allow_null=True, required=False)
    contact = serializers.CharField(source='Contact', allow_null=True, required=False)
    status = serializers.BooleanField(source='Status', allow_null=True, required=False)
    roleId = serializers.IntegerField(source='RoleId', allow_null=True, required=False)
    picture = serializers.CharField(source='Picture', allow_null=True, required=False)
    lastLoginTime = serializers.CharField(source='LastLoginTime', allow_null=True, required=False)
    password = serializers.CharField(source='Password', allow_null=True, required=False)
    fullAddress = serializers.CharField(source='FullAddress', allow_null=True, required=False)
    type = serializers.IntegerField(source='Type', allow_null=True, required=False)
    token = serializers.CharField(source='Token', allow_null=True, required=False)