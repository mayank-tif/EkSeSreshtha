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


class AnnouncementSaveAnnouncementRequestSerializer(RequestSerializer):
    Id = optional_int()
    Title = required_char()
    Description = required_char()
    ImageFile = serializers.ListField(child=serializers.FileField(), required=True)
    Image = optional_char()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()

# Center serializers ------------------------------------------------------------------------------------------------------------------------------

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
    id = serializers.IntegerField()
    centerName = serializers.CharField(allow_null=True, required=False)
    classStatus = serializers.BooleanField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    enrollmentDate = serializers.CharField(allow_null=True, required=False)
    vidhanSabhaId = serializers.IntegerField()
    districtId = serializers.IntegerField()
    panchayatId = serializers.IntegerField()
    villageId = serializers.IntegerField(allow_null=True, required=False)
    districtName = serializers.CharField(allow_null=True, required=False)
    vidhanSabhaName = serializers.CharField(allow_null=True, required=False)
    villageName = serializers.CharField(allow_null=True, required=False)
    panchayatName = serializers.CharField(allow_null=True, required=False)
    regionalAdminId = serializers.IntegerField(allow_null=True, required=False)
    regionalAdminName = serializers.CharField(allow_null=True, required=False)
    totalStudents = serializers.IntegerField(allow_null=True, required=False)
    teacher = serializers.DictField(allow_null=True, required=False)

class UserDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True, required=False)
    phoneNumber = serializers.CharField(allow_null=True, required=False)
    picture = serializers.CharField(allow_null=True, required=False)

class CenterAttendanceDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    centerName = serializers.CharField(allow_null=True, required=False)
    type = serializers.IntegerField()
    classStartedDate = serializers.DateTimeField(allow_null=True, required=False)
    classEndDate = serializers.DateTimeField(allow_null=True, required=False)
    totalStudents = serializers.IntegerField(allow_null=True, required=False)
    presentStudents = serializers.IntegerField(allow_null=True, required=False)
    regionalAdminName = serializers.CharField(allow_null=True, required=False)
    teacherName = serializers.CharField(allow_null=True, required=False)
    startDate = serializers.DateTimeField(allow_null=True, required=False)
    endDate = serializers.DateTimeField(allow_null=True, required=False)
    reason = serializers.CharField(allow_null=True, required=False)

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
    id = serializers.IntegerField()
    districtGuidId = serializers.CharField(allow_null=True, required=False)
    name = serializers.CharField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    createdOn = serializers.DateTimeField(allow_null=True, required=False)
    createdBy = serializers.IntegerField(allow_null=True, required=False)

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

class HolidaysDeleteHolidayByIdQuerySerializer(RequestSerializer):
    id = required_int()

class HolidaysDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True, required=False)
    description = serializers.CharField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    startDate = serializers.DateTimeField(allow_null=True, required=False)
    endDate = serializers.DateTimeField(allow_null=True, required=False)
    createdBy = serializers.IntegerField(allow_null=True, required=False)
    createdOn = serializers.DateTimeField(allow_null=True, required=False)
    centerId = serializers.IntegerField(allow_null=True, required=False)
    centerName = serializers.CharField(allow_null=True, required=False)

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
    id = serializers.IntegerField()
    panchayatGuidId = serializers.CharField(allow_null=True, required=False)
    name = serializers.CharField(allow_null=True, required=False)
    districtId = serializers.IntegerField()
    districtName = serializers.CharField(allow_null=True, required=False)
    vidhanSabhaId = serializers.IntegerField()
    vidhanSabhaName = serializers.CharField(allow_null=True, required=False)
    createdOn = serializers.DateTimeField(allow_null=True, required=False)
    createdBy = serializers.IntegerField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)

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
    id = serializers.IntegerField()
    enrollmentId = serializers.CharField(allow_null=True, required=False)
    fullName = serializers.CharField(allow_null=True, required=False)
    motherName = serializers.CharField(allow_null=True, required=False)
    fatherName = serializers.CharField(allow_null=True, required=False)
    age = serializers.IntegerField(allow_null=True, required=False)
    gender = serializers.CharField(allow_null=True, required=False)
    contact = serializers.CharField(allow_null=True, required=False)
    dateOfBirth = serializers.CharField(allow_null=True, required=False)
    email = serializers.CharField(allow_null=True, required=False)
    remarks = serializers.CharField(allow_null=True, required=False)
    grade = serializers.CharField(allow_null=True, required=False)
    phoneNumber = serializers.CharField(allow_null=True, required=False)
    profileImage = serializers.CharField(allow_null=True, required=False)
    whatsApp = serializers.CharField(allow_null=True, required=False)
    fullAddress = serializers.CharField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    joiningDate = serializers.DateTimeField(allow_null=True, required=False)
    centerName = serializers.CharField(allow_null=True, required=False)
    teacherName = serializers.CharField(allow_null=True, required=False)
    centerId = serializers.IntegerField()
    districtId = serializers.IntegerField()
    vidhanSabhaId = serializers.IntegerField()
    villageId = serializers.IntegerField(allow_null=True, required=False)
    panchayatId = serializers.IntegerField()
    fatherMobileNumber = serializers.CharField(allow_null=True, required=False)
    fatherOccupation = serializers.CharField(allow_null=True, required=False)
    motherMobileNumber = serializers.CharField(allow_null=True, required=False)
    motherOccupation = serializers.CharField(allow_null=True, required=False)
    category = serializers.CharField(allow_null=True, required=False)
    bpl = serializers.BooleanField(allow_null=True, required=False)
    schoolId = serializers.IntegerField(allow_null=True, required=False)
    schoolName = serializers.CharField(allow_null=True, required=False)

class StudentDetailDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    enrollmentId = serializers.CharField(allow_null=True, required=False)
    fullName = serializers.CharField(allow_null=True, required=False)
    motherName = serializers.CharField(allow_null=True, required=False)
    fatherName = serializers.CharField(allow_null=True, required=False)
    age = serializers.IntegerField(allow_null=True, required=False)
    gender = serializers.CharField(allow_null=True, required=False)
    contact = serializers.CharField(allow_null=True, required=False)
    dateOfBirth = serializers.CharField(allow_null=True, required=False)
    email = serializers.CharField(allow_null=True, required=False)
    remarks = serializers.CharField(allow_null=True, required=False)
    grade = serializers.CharField(allow_null=True, required=False)
    phoneNumber = serializers.CharField(allow_null=True, required=False)
    profileImage = serializers.CharField(allow_null=True, required=False)
    whatsApp = serializers.CharField(allow_null=True, required=False)
    fullAddress = serializers.CharField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    joiningDate = serializers.DateTimeField(allow_null=True, required=False)
    centerName = serializers.CharField(allow_null=True, required=False)
    teacherName = serializers.CharField(allow_null=True, required=False)
    centerId = serializers.IntegerField()
    districtId = serializers.IntegerField()
    vidhanSabhaId = serializers.IntegerField()
    villageId = serializers.IntegerField(allow_null=True, required=False)
    panchayatId = serializers.IntegerField()
    fatherMobileNumber = serializers.CharField(allow_null=True, required=False)
    fatherOccupation = serializers.CharField(allow_null=True, required=False)
    motherMobileNumber = serializers.CharField(allow_null=True, required=False)
    motherOccupation = serializers.CharField(allow_null=True, required=False)
    category = serializers.CharField(allow_null=True, required=False)
    bpl = serializers.BooleanField(allow_null=True, required=False)
    schoolId = serializers.IntegerField(allow_null=True, required=False)
    schoolName = serializers.CharField(allow_null=True, required=False)

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

class StudentAttendanceDetailDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    enrollmentId = serializers.CharField(allow_null=True, required=False)
    fullName = serializers.CharField(allow_null=True, required=False)
    attendanceStatus = serializers.CharField(allow_null=True, required=False)
    averageAttendance = serializers.DecimalField(allow_null=True, required=False, max_digits=10, decimal_places=2)
    date = serializers.DateTimeField(allow_null=True, required=False)

class StudentAbsentClassDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True, required=False)
    enrollmentId = serializers.CharField(allow_null=True, required=False)
    profileImage = serializers.CharField(allow_null=True, required=False)
    manualAttendance = serializers.IntegerField(allow_null=True, required=False)

class StudentAttendanceMonthDetailDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    fullName = serializers.CharField(allow_null=True, required=False)
    attendanceStatus = serializers.CharField(allow_null=True, required=False)
    date = serializers.DateTimeField(allow_null=True, required=False)
    
# School Serializers
class SchoolSaveSchoolRequestSerializer(RequestSerializer):
    Id = optional_int()
    SchoolName = required_char()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()

class SchoolDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    schoolName = serializers.CharField(allow_null=True, required=False)
    createdOn = serializers.DateTimeField(allow_null=True, required=False)
    createdBy = serializers.IntegerField(allow_null=True, required=False)


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


class UserSaveUserRequestSerializer(UserSaveSuperAdminRequestSerializer):
    foreign_key_fields = {
        "VidhanSabhaId": VidhanSabha,
        "DistrictId": District,
        "VillageId": Village,
    }

    DeviceId = optional_char()
    Education = optional_char()
    VidhanSabhaId = optional_int()
    DistrictId = optional_int()
    VillageId = optional_int()
    AssignedTeacherStatus = optional_bool()
    AssignedRegionalAdminStatus = optional_bool()
    GuardianName = optional_char()
    GuardianNumber = optional_char()
    ListOfPanchayatIds = serializers.ListField(child=serializers.IntegerField(), required=False)
    WhatsApp = required_char()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        panchayat_ids = attrs.get("ListOfPanchayatIds") or []
        existing_ids = set(Panchayat.objects.filter(pk__in=panchayat_ids).values_list("id", flat=True))
        missing_ids = [value for value in panchayat_ids if value not in existing_ids]
        if missing_ids:
            raise serializers.ValidationError({"ListOfPanchayatIds": f"Panchayat ids do not exist: {missing_ids}"})
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
    mobileNumber = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    
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
    deviceId = serializers.CharField(required=True)

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

class UserSaveUserRequestSerializer(UserSaveSuperAdminRequestSerializer):
    foreign_key_fields = {
        "VidhanSabhaId": VidhanSabha,
        "DistrictId": District,
        "VillageId": Village,
    }
    DeviceId = optional_char()
    Education = optional_char()
    VidhanSabhaId = optional_int()
    DistrictId = optional_int()
    VillageId = optional_int()
    AssignedTeacherStatus = optional_bool()
    AssignedRegionalAdminStatus = optional_bool()
    GuardianName = optional_char()
    GuardianNumber = optional_char()
    ListOfPanchayatIds = serializers.ListField(child=serializers.IntegerField(), required=False)
    WhatsApp = required_char()

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
    id = serializers.IntegerField()
    vidhanSabhaGuidId = serializers.CharField(allow_null=True, required=False)
    name = serializers.CharField(allow_null=True, required=False)
    districtId = serializers.IntegerField()
    districtName = serializers.CharField(allow_null=True, required=False)
    createdOn = serializers.DateTimeField(allow_null=True, required=False)
    createdBy = serializers.IntegerField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)


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
    id = serializers.IntegerField()
    villageGuidId = serializers.CharField(allow_null=True, required=False)
    name = serializers.CharField(allow_null=True, required=False)
    districtId = serializers.IntegerField()
    districtName = serializers.CharField(allow_null=True, required=False)
    vidhanSabhaId = serializers.IntegerField()
    vidhanSabhaName = serializers.CharField(allow_null=True, required=False)
    panchayatId = serializers.IntegerField()
    panchayatName = serializers.CharField(allow_null=True, required=False)
    createdOn = serializers.DateTimeField(allow_null=True, required=False)
    createdBy = serializers.IntegerField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)

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

class TeacherDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    fullName = serializers.CharField(allow_null=True, required=False)
    age = serializers.IntegerField(allow_null=True, required=False)
    gender = serializers.CharField(allow_null=True, required=False)
    dateOfBirth = serializers.CharField(allow_null=True, required=False)
    phoneNumber = serializers.CharField(allow_null=True, required=False)
    whatsApp = serializers.CharField(allow_null=True, required=False)
    email = serializers.CharField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    count = serializers.IntegerField(allow_null=True, required=False)
    picture = serializers.CharField(allow_null=True, required=False)
    password = serializers.CharField(allow_null=True, required=False)
    fullAddress = serializers.CharField(allow_null=True, required=False)
    education = serializers.CharField(allow_null=True, required=False)
    token = serializers.CharField(allow_null=True, required=False)


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

class RegionalAdminDtoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    regionalAdminGuidId = serializers.CharField(allow_null=True, required=False)
    fullName = serializers.CharField(allow_null=True, required=False)
    age = serializers.IntegerField(allow_null=True, required=False)
    gender = serializers.CharField(allow_null=True, required=False)
    dateOfBirth = serializers.CharField(allow_null=True, required=False)
    phoneNumber = serializers.CharField(allow_null=True, required=False)
    whatsApp = serializers.CharField(allow_null=True, required=False)
    email = serializers.CharField(allow_null=True, required=False)
    contact = serializers.CharField(allow_null=True, required=False)
    status = serializers.BooleanField(allow_null=True, required=False)
    roleId = serializers.IntegerField(allow_null=True, required=False)
    picture = serializers.CharField(allow_null=True, required=False)
    lastLoginTime = serializers.CharField(allow_null=True, required=False)
    password = serializers.CharField(allow_null=True, required=False)
    fullAddress = serializers.CharField(allow_null=True, required=False)
    type = serializers.IntegerField(allow_null=True, required=False)
    token = serializers.CharField(allow_null=True, required=False)
