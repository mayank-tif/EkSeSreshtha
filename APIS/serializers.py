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


class SwaggerRequestSerializer(serializers.Serializer):
    foreign_key_fields = {}
    foreign_key_list_fields = {}

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


class PaginationQuerySerializer(SwaggerRequestSerializer):
    offset = optional_int()
    limit = optional_int()


class IdQuerySerializer(SwaggerRequestSerializer):
    id = required_int()


class AnnouncementSaveAnnouncementRequestSerializer(SwaggerRequestSerializer):
    Id = optional_int()
    Title = required_char()
    Description = required_char()
    ImageFile = serializers.ListField(child=serializers.FileField(), required=True)
    Image = optional_char()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()


class CenterSaveCenterRequestSerializer(SwaggerRequestSerializer):
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


class CenterGetCenteryIdQuerySerializer(SwaggerRequestSerializer):
    centeId = required_int()


class CenterGetAllCentersQuerySerializer(SwaggerRequestSerializer):
    userId = optional_int()
    type = optional_int()


class CenterGetAllCentersByStatusQuerySerializer(SwaggerRequestSerializer):
    status = optional_bool()
    userId = optional_int()


class CenterGetCenterByTeacherIdQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"userId": Teacher}
    userId = required_int()


class CenterGetAllCenterAttendanceQuerySerializer(PaginationQuerySerializer):
    userId = optional_int()
    date = optional_datetime()


class CenterUpdateCenterActiveOrDeactiveQuerySerializer(SwaggerRequestSerializer):
    centerId = required_int()
    status = optional_bool()
    userId = optional_int()
    reason = optional_char()


class CenterGetTotalAttendanceCountOfCenterQuerySerializer(SwaggerRequestSerializer):
    userId = optional_int()
    date = optional_datetime()


class ClassSaveClassRequestSerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"CenterId": Center}

    Id = optional_int()
    ClassEnrolmentId = optional_char()
    Name = required_char()
    CenterId = required_int()
    UserId = required_int()
    TotalStudents = required_int()
    AvilableStudents = required_int()


class ClassCancelClassRequestSerializer(SwaggerRequestSerializer):
    Id = required_int()
    Reason = required_char()
    CancelBy = required_int()


class ClassUpdateEndClassTimeRequestSerializer(SwaggerRequestSerializer):
    Id = required_int()


class ClassUpdateClassSubStatusRequestSerializer(SwaggerRequestSerializer):
    Id = required_int()
    SubStatus = optional_int()


class ClassCancelClassByTeacherRequestSerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"CenterId": Center}

    Id = optional_int()
    CenterId = required_int()
    StartingDate = required_datetime()
    EndingDate = required_datetime()
    CreatedOn = optional_datetime()
    UsersId = required_int()
    Reason = optional_char()


class ClassDeleteClassByTeacherIdQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"classId": ClassModel}
    classId = required_int()


class ClassGetClassCurrentStatusQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"centerId": Center, "teacherId": Teacher}
    centerId = required_int()
    teacherId = required_int()


class ClassGetLiveClassDetailQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"classId": ClassModel}
    classId = required_int()


class DashboardCenterDateRangeQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"centerId": Center}
    centerId = optional_int()
    startDate = optional_datetime()
    endDate = optional_datetime()


class DashboardGetCenterDetailByMonthQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"centerId": Center}
    centerId = optional_int()
    month = optional_int()
    year = optional_int()


class DashboardFilterQuerySerializer(SwaggerRequestSerializer):
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


class DashboardDistrictOfCenterByFilterQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"districtId": District, "vidhanSabhaId": VidhanSabha}
    districtId = optional_int()
    vidhanSabhaId = optional_int()
    startDate = optional_datetime()
    endDate = optional_datetime()


class DistrictSaveDistrictRequestSerializer(SwaggerRequestSerializer):
    Id = optional_int()
    DistrictGuidId = optional_char()
    Name = required_char()
    Status = optional_bool()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()


class FileSendNotificationRequestSerializer(SwaggerRequestSerializer):
    userId = optional_int()
    DeviceId = optional_char()
    ListOfDeviceIds = serializers.ListField(child=serializers.CharField(), required=False)
    IsAndroiodDevice = optional_bool()
    Title = optional_char()
    Body = optional_char()


class FileUploadProfileImageRequestSerializer(SwaggerRequestSerializer):
    files = serializers.ListField(child=serializers.FileField(), required=False)


class HolidaysSaveHolidaysRequestSerializer(SwaggerRequestSerializer):
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


class HolidaysTeacherIdQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"teacherId": Teacher}
    teacherId = required_int()


class HolidaysCenterIdQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"centerId": Center}
    centerId = required_int()


class HolidaysYearQuerySerializer(SwaggerRequestSerializer):
    year = required_int()


class HolidaysGetAllHolidaysQuerySerializer(SwaggerRequestSerializer):
    status = optional_bool()
    userId = optional_int()


class HolidaysDeleteHolidayByIdQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"id": Holidays}
    id = required_int()


class PanchayatSavePanchayatRequestSerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"DistrictId": District, "VidhanSabhaId": VidhanSabha}

    Id = optional_int()
    PanchayatGuidId = optional_char()
    Name = required_char()
    Status = optional_bool()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()
    DistrictId = required_int()
    VidhanSabhaId = required_int()


class PanchayatByDistrictAndVidhanSabhaQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"districtId": District, "vidhanSabhaId": VidhanSabha}
    districtId = required_int()
    vidhanSabhaId = required_int()


class NameCheckQuerySerializer(SwaggerRequestSerializer):
    name = required_char()


class SchoolSaveSchoolRequestSerializer(SwaggerRequestSerializer):
    Id = optional_int()
    SchoolName = required_char()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()


class StudentSaveStudentRequestSerializer(SwaggerRequestSerializer):
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


class StudentGetStudentByIdQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"studentId": Student}
    studentId = required_int()


class StudentUpdateStudentActiveOrInactiveRequestSerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"Id": Student}
    Id = required_int()
    Status = required_bool()


class StudentGetTotalStudentPresentQuerySerializer(SwaggerRequestSerializer):
    scanDate = optional_datetime()
    userId = optional_int()


class StudentGetAllStudentsQuerySerializer(SwaggerRequestSerializer):
    userId = optional_int()
    districtId = optional_int()
    vidhanSabhaId = optional_int()
    panchayatId = optional_int()
    villageId = optional_int()


class StudentAttendanceSaveRequestSerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"ClassId": ClassModel, "CenterId": Center}
    foreign_key_list_fields = {"StudentIds": Student}

    Id = optional_int()
    ClassId = required_int()
    UserId = required_int()
    StudentIds = serializers.ListField(child=serializers.IntegerField(), required=True, allow_empty=False)
    ScanDate = required_datetime()
    CenterId = required_int()


class StudentAttendanceCenterQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"centerId": Center}
    centerId = required_int()


class StudentAttendanceStatusQuerySerializer(StudentAttendanceCenterQuerySerializer):
    scanDate = optional_datetime()


class StudentAttendanceByMonthQuerySerializer(StudentAttendanceCenterQuerySerializer):
    studentId = optional_int()
    month = optional_int()
    year = optional_int()


class UserSaveSuperAdminRequestSerializer(SwaggerRequestSerializer):
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


class UserUpdateDeviceIdRequestSerializer(SwaggerRequestSerializer):
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


class UserGetUserByIdQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"userId": User}
    userId = required_int()


class UserGetUserDetailByPhoneNumberQuerySerializer(SwaggerRequestSerializer):
    phoneNumer = required_char()


class UserUpdatePasswordQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"userId": User}
    userId = required_int()
    newPassword = required_char()


class UserGetAllTeachersQuerySerializer(SwaggerRequestSerializer):
    userId = optional_int()


class UserSearchDataQuerySerializer(SwaggerRequestSerializer):
    type = optional_char()
    queryString = optional_char()


class VidhanSabhaSaveVidhanSabhaRequestSerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"DistrictId": District}

    Id = optional_int()
    VidhanSabhaGuidId = optional_char()
    Name = required_char()
    Status = optional_bool()
    CreatedOn = optional_datetime()
    CreatedBy = optional_int()
    DistrictId = required_int()


class VidhanSabhaByDistrictIdQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {"districtId": District}
    districtId = required_int()


class VillageSaveVillageRequestSerializer(SwaggerRequestSerializer):
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


class VillageByDistrictVidhanSabhaAndPanchayatQuerySerializer(SwaggerRequestSerializer):
    foreign_key_fields = {
        "districtId": District,
        "vidhanSabhaId": VidhanSabha,
        "panchayatId": Panchayat,
    }

    districtId = required_int()
    vidhanSabhaId = required_int()
    panchayatId = required_int()


class TeacherSaveTeacherRequestSerializer(SwaggerRequestSerializer):
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


class RegionalAdminSaveRegionalAdminRequestSerializer(TeacherSaveTeacherRequestSerializer):
    RegionalAdminGuidId = optional_char()
    RoleId = optional_int()
    Contact = optional_char()
    Type = optional_int()


class LoginRequestSerializer(LoginSerializer):
    pass

