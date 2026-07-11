import hashlib
import logging
import uuid
from datetime import timedelta

from django.core.files.storage import default_storage
from django.db import IntegrityError
from django.db.models import Avg, Count, Q
from django.forms.models import model_to_dict
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView

from EkSeSreshtha.env_details import *
from . import serializers as api_serializers
from .models import *
from .serializers import GenerateAppTokenSerializer, LoginSerializer, UserLoginResponseSerializer
from .utils import validate_app_and_device_with_token


logger = logging.getLogger(__name__)

SUPER_ADMIN = 1
REGIONAL_ADMIN = 2
TEACHER = 3

SHA256_HEX_LENGTH = 64


class DummyUser:
    """Minimal user-like object used only for issuing the app access token."""
    def __init__(self, username):
        self.username = username
        self.id = 1


def ok(data=None, message="Success", code=status.HTTP_200_OK, extra=None):
    payload = {"status": True, "message": message, "code": code}
    if data is not None:
        payload["data"] = data
    if extra:
        payload.update(extra)
    return Response(payload, status=code)


def fail(message="Not found", code=status.HTTP_404_NOT_FOUND, data=None, error_key="error"):
    payload = {"status": False, error_key: message, "code": code}
    if data is not None:
        payload["data"] = data
    return Response(payload, status=code)


def request_value(request, *names, default=None):
    for source in (request.data, request.query_params):
        for name in names:
            if name in source and source.get(name) not in ("", None):
                return source.get(name)
    return default


def to_bool(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "active"}


def to_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def hash_password(password):
    if password in (None, ""):
        return password
    password = str(password)
    if len(password) == SHA256_HEX_LENGTH and all(ch in "0123456789abcdefABCDEF" for ch in password):
        return password.lower()
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def parse_any_datetime(value):
    if value in (None, ""):
        return None
    parsed = parse_datetime(str(value))
    if parsed:
        return parsed
    parsed_date = parse_date(str(value))
    return parsed_date


def apply_pagination(queryset, request):
    offset = to_int(request_value(request, "offset", "Offset"), 0)
    limit = to_int(request_value(request, "limit", "Limit"), 0)
    if limit > 0:
        return queryset[offset : offset + limit]
    if offset > 0:
        return queryset[offset:]
    return queryset


def model_payload(obj, exclude_sensitive=True):
    if obj is None:
        return None
    payload = model_to_dict(obj)
    payload["id"] = obj.pk
    if exclude_sensitive:
        payload.pop("password", None)
    return payload


def queryset_payload(queryset):
    return [model_payload(obj) for obj in queryset]


def format_dotnet_datetime(value):
    if not value:
        return None
    if isinstance(value, str):
        return value
    hour = value.strftime("%I").lstrip("0") or "0"
    return f"{value.month}/{value.day}/{value.year} {hour}:{value:%M:%S %p}"


def model_field_input_names(field):
    names = {field.name, field.attname, field.db_column}
    parts = field.name.split("_")
    camel = parts[0] + "".join(part.title() for part in parts[1:])
    pascal = "".join(part.title() for part in parts)
    names.update({camel, pascal})
    if field.name.endswith("_guid_id"):
        names.add(field.db_column)
    return [name for name in names if name]


def coerce_for_field(field, value):
    if value in ("", "null", "None"):
        return None
    internal_type = field.get_internal_type()
    if internal_type in {"IntegerField", "AutoField", "BigAutoField"}:
        return int(value)
    if internal_type == "BooleanField":
        return to_bool(value)
    if internal_type == "DateTimeField":
        return parse_any_datetime(value)
    if internal_type == "FloatField":
        return float(value)
    return value


def data_for_model(model, request, defaults=None):
    defaults = defaults or {}
    values = {}
    for field in model._meta.fields:
        if field.primary_key:
            continue
        for input_name in model_field_input_names(field):
            value = request_value(request, input_name)
            if value is not None:
                target_name = field.attname if field.is_relation else field.name
                values[target_name] = coerce_for_field(field, value)
                break
    for key, value in defaults.items():
        values.setdefault(key, value)
    return values


def save_model_from_request(model, request, defaults=None, lookup_id_names=("id", "Id")):
    values = data_for_model(model, request, defaults=defaults)
    if "password" in values:
        values["password"] = hash_password(values["password"])
    object_id = request_value(request, *lookup_id_names)
    if object_id:
        obj, _ = model.objects.update_or_create(pk=object_id, defaults=values)
    else:
        obj = model.objects.create(**values)
    return obj


def get_by_id(model, request, *names):
    object_id = request_value(request, *names, "id", "Id")
    if not object_id:
        return None
    return model.objects.filter(pk=object_id).first()


def filter_if_present(queryset, request, field_name, *param_names):
    value = request_value(request, *param_names)
    if value not in (None, "", "0", 0):
        return queryset.filter(**{field_name: value})
    return queryset


def login_response(account, account_type, mobile_number):
    token = AccessToken()
    token["user_id"] = account.id
    token["user_type"] = account_type
    token["mobile_number"] = mobile_number
    token["name"] = getattr(account, "full_name", None) or getattr(account, "name", None) or mobile_number
    token.set_exp(lifetime=timedelta(days=30))
    account.last_login_time = format_dotnet_datetime(now())
    if hasattr(account, "token"):
        account.token = str(token)
        account.save(update_fields=["last_login_time", "token"])
    else:
        account.save(update_fields=["last_login_time"])
    if isinstance(account, User):
        serializer = UserLoginResponseSerializer(account, context={"token": str(token)})
        return ok(data=serializer.data, message="Login successfully")
    data = model_payload(account)
    data["user_type"] = account_type
    return ok(data=data, message="Login successfully")


class DotNetAPIView(APIView):
    """Base DRF view for .NET-compatible endpoints with shared parsers and error logging."""
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    serializer_class = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.validate_request_serializer(request)

    def get_request_serializer(self, request):
        if self.serializer_class is None:
            return None
        data = request.query_params if request.method in {"GET", "DELETE"} else request.data
        if request.method not in {"GET", "DELETE"} and not data:
            data = request.query_params
        return self.serializer_class(data=data)

    def validate_request_serializer(self, request):
        serializer = self.get_request_serializer(request)
        if serializer is None:
            return
        serializer.is_valid(raise_exception=True)
        self.validated_request_data = serializer.validated_data

    def handle_exception(self, exc):
        logger.exception("%s failed", self.__class__.__name__)
        if isinstance(exc, serializers.ValidationError):
            return fail("Validation failed", code=status.HTTP_400_BAD_REQUEST, data=exc.detail)
        if isinstance(exc, IntegrityError):
            return fail(str(exc), code=status.HTTP_409_CONFLICT)
        return fail(str(exc), code=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
class GenerateAppTokenView(TokenObtainPairView):
    """Issues the short-lived application token after validating API headers."""
    serializer_class = GenerateAppTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        username = request.headers.get("Username")
        password = request.headers.get("Password")

        if username != API_USERNAME or password != API_PASSWORD:
            return Response({"message": "Invalid username or password"}, status=status.HTTP_401_UNAUTHORIZED)

        serializer.is_valid(raise_exception=True)
        user = DummyUser(username)
        token = AccessToken.for_user(user)
        token["deviceid"] = request.data.get("deviceid")
        token["username"] = username
        token.set_exp(lifetime=timedelta(minutes=15))
        return Response({"access_token": str(token)}, status=status.HTTP_200_OK)


class LoginAPIView(DotNetAPIView):
    """Authenticates a user, teacher, or regional admin using the hashed password flow."""
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        logger.info("LoginAPIView started")
        validate_app_and_device_with_token(request)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile_number = serializer.validated_data["mobileNumber"]
        password = hash_password(serializer.validated_data["password"])
        logger.info("Attempting login for mobile number: %s", mobile_number)

        account = User.objects.filter(phone_number=mobile_number, password=password).first()
        if account:
            return login_response(account, "super_admin", mobile_number)
        account = Teacher.objects.filter(phone_number=mobile_number, password=password).first()
        if account:
            return login_response(account, "teacher", mobile_number)
        account = RegionalAdmin.objects.filter(phone_number=mobile_number, password=password).first()
        if account:
            return login_response(account, "regional_admin", mobile_number)
        return fail("invalid credential", code=status.HTTP_404_NOT_FOUND)


class ModelSaveView(DotNetAPIView):
    """Generic class-based create/update view for simple model-backed POST endpoints."""
    model = None
    success_message = "Data save successfully"
    not_found_message = "data doesn't save"
    guid_field = None

    def post(self, request, *args, **kwargs):
        defaults = {}
        if self.guid_field:
            defaults[self.guid_field] = str(uuid.uuid4())
        obj = save_model_from_request(self.model, request, defaults=defaults)
        return ok(model_payload(obj), self.success_message)


class ModelListView(DotNetAPIView):
    """Generic class-based list view with optional offset/limit pagination."""
    model = None
    message = "List"

    def get_queryset(self, request):
        return self.model.objects.all().order_by("id")

    def get(self, request, *args, **kwargs):
        data = queryset_payload(apply_pagination(self.get_queryset(request), request))
        return ok(data, self.message)


class ModelDetailView(DotNetAPIView):
    """Generic class-based detail view that returns a single record by id."""
    model = None
    id_names = ("id", "Id")
    found_message = "Data exists"
    missing_message = "Data not exists"

    def get(self, request, *args, **kwargs):
        obj = get_by_id(self.model, request, *self.id_names)
        if obj:
            return ok(model_payload(obj), self.found_message)
        return fail(self.missing_message, data={})


class NameExistsView(DotNetAPIView):
    """Generic helper view for name availability checks used by location masters."""
    model = None
    exists_message = "Name already exists"
    missing_message = "Name doesn't exists"

    def post(self, request, *args, **kwargs):
        name = request_value(request, "name", "Name")
        exists = self.model.objects.filter(name__iexact=name).exists() if name else False
        if exists:
            return ok(message=self.exists_message, extra={"status": False})
        return fail(self.missing_message)


class AnnouncementSaveannouncementPostView(ModelSaveView):
    """Saves or updates announcement records from form or JSON data."""
    serializer_class = api_serializers.AnnouncementSaveAnnouncementRequestSerializer
    model = Announcement
    success_message = "Announcement save successfully"


class AnnouncementGetannouncementGetView(ModelListView):
    """Returns the announcement list ordered by the model defaults."""
    model = Announcement
    message = "List of announcement"


class CenterSavecenterPostView(ModelSaveView):
    """Saves or updates a center and creates a guid when needed."""
    serializer_class = api_serializers.CenterSaveCenterRequestSerializer
    model = Center
    guid_field = "center_guid_id"
    success_message = "Center save successfully"


class CommonCheckusermobilenumberPostView(CenterSavecenterPostView):
    """Compatibility alias for the .NET Common/CheckUserMobileNumber route."""
    serializer_class = api_serializers.CenterSaveCenterRequestSerializer


class CenterGetcenteryidGetView(ModelDetailView):
    """Returns a single center by the legacy centeId query parameter."""
    serializer_class = api_serializers.CenterGetCenteryIdQuerySerializer
    model = Center
    id_names = ("centeId", "centerId", "CenterId")
    found_message = "center exists"
    missing_message = "center not exists"


class CenterGetallcentersGetView(ModelListView):
    """Lists centers, optionally narrowing the result to a teacher/user."""
    serializer_class = api_serializers.CenterGetAllCentersQuerySerializer
    model = Center
    message = "List of centers"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = filter_if_present(queryset, request, "teachers__id", "userId", "UserId")
        return queryset.distinct()


class CenterGetallcentersbystatusGetView(ModelListView):
    """Lists centers filtered by active/inactive status."""
    serializer_class = api_serializers.CenterGetAllCentersByStatusQuerySerializer
    model = Center
    message = "Student attendance of centers"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        value = request_value(request, "status", "Status")
        if value is not None:
            queryset = queryset.filter(status=to_bool(value))
        return queryset


class CenterGetcenterbyteacheridGetView(DotNetAPIView):
    """Returns the center assigned to a teacher."""
    serializer_class = api_serializers.CenterGetCenterByTeacherIdQuerySerializer

    def get(self, request, *args, **kwargs):
        user_id = request_value(request, "userId", "teacherId", "UserId")
        teacher = Teacher.objects.filter(pk=user_id).first()
        center = teacher.center if teacher else None
        if center:
            return ok(model_payload(center), "center detail")
        return fail("center detail not found", data=None)


class CenterGetallcenterattendanceGetView(DotNetAPIView):
    """Returns center records with attendance and student counts for a date."""
    serializer_class = api_serializers.CenterGetAllCenterAttendanceQuerySerializer

    def get(self, request, *args, **kwargs):
        scan_date = parse_any_datetime(request_value(request, "date", "scanDate"))
        queryset = Center.objects.all().order_by("id")
        data = []
        for center in apply_pagination(queryset, request):
            attendance = StudentAttendance.objects.filter(center=center)
            if scan_date:
                attendance = attendance.filter(scan_date__date=scan_date)
            payload = model_payload(center)
            payload["attendance_count"] = attendance.count()
            payload["student_count"] = Student.objects.filter(center=center).count()
            data.append(payload)
        return ok(data, "Centers avilable")


class CenterUpdatecenteractiveordeactiveGetView(DotNetAPIView):
    """Toggles or sets center status and records the reason in CenterLog."""
    serializer_class = api_serializers.CenterUpdateCenterActiveOrDeactiveQuerySerializer

    def get(self, request, *args, **kwargs):
        center_id = request_value(request, "centerId", "CenterId")
        center = Center.objects.filter(pk=center_id).first()
        if not center:
            return ok(message="Center status not updated")
        status_value = request_value(request, "status", "Status")
        center.status = to_bool(status_value) if status_value is not None else not bool(center.status)
        center.save(update_fields=["status"])
        CenterLog.objects.create(
            center=center,
            user_id=to_int(request_value(request, "userId", "UserId"), 0) or None,
            reason=request_value(request, "reason", "Reason"),
        )
        return ok(message="Center status updated")


class CenterGettotalattendancecountofcenterGetView(DotNetAPIView):
    """Returns aggregate attendance, student, and center counts."""
    serializer_class = api_serializers.CenterGetTotalAttendanceCountOfCenterQuerySerializer

    def get(self, request, *args, **kwargs):
        scan_date = parse_any_datetime(request_value(request, "date", "scanDate"))
        attendance = StudentAttendance.objects.all()
        if scan_date:
            attendance = attendance.filter(scan_date__date=scan_date)
        data = {
            "totalAttendance": attendance.count(),
            "totalStudents": Student.objects.count(),
            "totalCenters": Center.objects.count(),
        }
        return ok(data, "Center exists")


class ClassSaveclassPostView(ModelSaveView):
    """Creates or updates a class and assigns default class identifiers/status."""
    serializer_class = api_serializers.ClassSaveClassRequestSerializer
    model = ClassModel
    guid_field = "class_enrolment_id"
    success_message = "Class save successfully"

    def post(self, request, *args, **kwargs):
        defaults = {"class_enrolment_id": str(uuid.uuid4()), "sub_status": 0}
        obj = save_model_from_request(ClassModel, request, defaults=defaults)
        return ok(model_payload(obj), self.success_message)


class ClassCancelclassPostView(DotNetAPIView):
    """Cancels a class by setting status, reason, cancel user, and cancel date."""
    serializer_class = api_serializers.ClassCancelClassRequestSerializer

    def post(self, request, *args, **kwargs):
        class_id = request_value(request, "classId", "ClassId", "id", "Id")
        obj = ClassModel.objects.filter(pk=class_id).first()
        if not obj:
            return fail("Class not canceled")
        obj.status = 0
        obj.reason = request_value(request, "reason", "Reason")
        obj.cancel_by = to_int(request_value(request, "cancelBy", "CancelBy"), 0) or None
        obj.cancel_date = now()
        obj.save(update_fields=["status", "reason", "cancel_by", "cancel_date"])
        return ok(message="Class canceled successfully")


class ClassUpdateendclasstimePostView(DotNetAPIView):
    """Updates the end time for a class."""
    serializer_class = api_serializers.ClassUpdateEndClassTimeRequestSerializer

    def post(self, request, *args, **kwargs):
        obj = get_by_id(ClassModel, request, "classId", "ClassId")
        if not obj:
            return fail("Time not updated")
        obj.end_date = parse_any_datetime(request_value(request, "endDate", "EndDate")) or now()
        obj.save(update_fields=["end_date"])
        return ok(message="Time updated")


class ClassUpdateclasssubstatusPostView(DotNetAPIView):
    """Updates the class sub-status value."""
    serializer_class = api_serializers.ClassUpdateClassSubStatusRequestSerializer

    def post(self, request, *args, **kwargs):
        obj = get_by_id(ClassModel, request, "classId", "ClassId")
        if not obj:
            return fail("Status not updated")
        obj.sub_status = to_int(request_value(request, "subStatus", "SubStatus"), obj.sub_status)
        obj.save(update_fields=["sub_status"])
        return ok(message="Status updated")


class ClassCancelclassbyteacherPostView(ModelSaveView):
    """Records a teacher-requested class cancellation."""
    serializer_class = api_serializers.ClassCancelClassByTeacherRequestSerializer
    model = ClassCancelByTeacher
    success_message = "Class cancelled"


class ClassDeleteclassbyteacheridPostView(DotNetAPIView):
    """Deletes a class by class id for legacy API compatibility."""
    serializer_class = api_serializers.ClassDeleteClassByTeacherIdQuerySerializer

    def post(self, request, *args, **kwargs):
        obj = get_by_id(ClassModel, request, "classId", "ClassId")
        if not obj:
            return fail("class  not deleted")
        obj.delete()
        return ok(message="class deleted")


class ClassGetclasscurrentstatusGetView(DotNetAPIView):
    """Returns currently open classes for a center and optional teacher."""
    serializer_class = api_serializers.ClassGetClassCurrentStatusQuerySerializer

    def get(self, request, *args, **kwargs):
        center_id = request_value(request, "centerId", "CenterId")
        teacher_id = request_value(request, "teacherId", "TeacherId")
        queryset = ClassModel.objects.filter(center_id=center_id, end_date__isnull=True)
        if teacher_id:
            queryset = queryset.filter(users_id=teacher_id)
        return ok(queryset_payload(queryset), "class status")


class ClassGetliveclassdetailGetView(ModelDetailView):
    """Returns live class detail for a class id."""
    serializer_class = api_serializers.ClassGetLiveClassDetailQuerySerializer
    model = ClassModel
    id_names = ("classId", "ClassId")
    found_message = "class detail exists"
    missing_message = "Class detail not exists"


class DistrictGetalldistrictGetView(ModelListView):
    """Lists districts with optional offset/limit pagination."""
    serializer_class = api_serializers.PaginationQuerySerializer
    model = District
    message = "List of district"


class DistrictSavedistrictPostView(ModelSaveView):
    """Saves or updates a district and creates a guid when needed."""
    serializer_class = api_serializers.DistrictSaveDistrictRequestSerializer
    model = District
    guid_field = "district_guid_id"
    success_message = "District save successfully"


class VidhansabhaGetallvidhansabhaGetView(ModelListView):
    """Lists Vidhan Sabha records with optional pagination."""
    serializer_class = api_serializers.PaginationQuerySerializer
    model = VidhanSabha
    message = "List of vidhanSabha"


class VidhansabhaSavevidhansabhaPostView(ModelSaveView):
    """Saves or updates a Vidhan Sabha record."""
    serializer_class = api_serializers.VidhanSabhaSaveVidhanSabhaRequestSerializer
    model = VidhanSabha
    guid_field = "vidhan_sabha_guid_id"
    success_message = "VidanSabha save successfully"


class VidhansabhaGetvidhansabhabydistrictidGetView(ModelListView):
    """Lists Vidhan Sabha records for a district."""
    serializer_class = api_serializers.VidhanSabhaByDistrictIdQuerySerializer
    model = VidhanSabha
    message = "VidanSabha exists"

    def get_queryset(self, request):
        return VidhanSabha.objects.filter(district_id=request_value(request, "districtId", "DistrictId"))


class VidhansabhaCheckvidhansabhanamePostView(NameExistsView):
    """Checks whether a Vidhan Sabha name already exists."""
    serializer_class = api_serializers.NameCheckQuerySerializer
    model = VidhanSabha
    exists_message = "VidhanSabha name already exists"
    missing_message = "VidhanSabha name doesn't exists"


class PanchayatGetallpanchayatGetView(ModelListView):
    """Lists panchayats with optional pagination."""
    serializer_class = api_serializers.PaginationQuerySerializer
    model = Panchayat
    message = "List of panchayat"


class PanchayatSavepanchayatPostView(ModelSaveView):
    """Saves or updates a panchayat record."""
    serializer_class = api_serializers.PanchayatSavePanchayatRequestSerializer
    model = Panchayat
    guid_field = "panchayat_guid_id"
    success_message = "Panchayat save successfully"


class PanchayatGetpanchayatbydistrictandvidhansabhaidGetView(ModelListView):
    """Lists panchayats for a district and Vidhan Sabha."""
    serializer_class = api_serializers.PanchayatByDistrictAndVidhanSabhaQuerySerializer
    model = Panchayat
    message = "Panchayat exists"

    def get_queryset(self, request):
        return Panchayat.objects.filter(
            district_id=request_value(request, "districtId", "DistrictId"),
            vidhan_sabha_id=request_value(request, "vidhanSabhaId", "VidhanSabhaId"),
        )


class PanchayatCheckpanchayatnamePostView(NameExistsView):
    """Checks whether a panchayat name already exists."""
    serializer_class = api_serializers.NameCheckQuerySerializer
    model = Panchayat
    exists_message = "Panchayat name already exists"
    missing_message = "Panchayat name doesn't exists"


class VillageGetallvillageGetView(ModelListView):
    """Lists villages with optional pagination."""
    serializer_class = api_serializers.PaginationQuerySerializer
    model = Village
    message = "List of village"


class VillageSavevillagePostView(ModelSaveView):
    """Saves or updates a village record."""
    serializer_class = api_serializers.VillageSaveVillageRequestSerializer
    model = Village
    guid_field = "village_guid_id"
    success_message = "Village save successfully"


class VillageGetvillagebydistrictvidhansabhaandpanchidGetView(ModelListView):
    """Lists villages by district, Vidhan Sabha, and panchayat."""
    serializer_class = api_serializers.VillageByDistrictVidhanSabhaAndPanchayatQuerySerializer
    model = Village
    message = "Village exists"

    def get_queryset(self, request):
        return Village.objects.filter(
            district_id=request_value(request, "districtId", "DistrictId"),
            vidhan_sabha_id=request_value(request, "vidhanSabhaId", "VidhanSabhaId"),
            panchayat_id=request_value(request, "panchayatId", "PanchayatId"),
        )


class VillageCheckvillagenamePostView(NameExistsView):
    """Checks whether a village name already exists."""
    serializer_class = api_serializers.NameCheckQuerySerializer
    model = Village
    exists_message = "Village name already exists"
    missing_message = "Village name doesn't exists"


class SchoolSaveschoolPostView(ModelSaveView):
    """Saves or updates a school record."""
    serializer_class = api_serializers.SchoolSaveSchoolRequestSerializer
    model = School
    success_message = "School save successfully"


class SchoolGetallschoolsGetView(ModelListView):
    """Returns all school records."""
    model = School
    message = "List of schools"


class HolidaysSaveholidaysPostView(ModelSaveView):
    """Saves or updates holiday records."""
    serializer_class = api_serializers.HolidaysSaveHolidaysRequestSerializer
    model = Holidays
    success_message = "Holiday save successfully"


class HolidaysGetallholidaysGetView(ModelListView):
    """Lists holidays, optionally filtered by status."""
    serializer_class = api_serializers.HolidaysGetAllHolidaysQuerySerializer
    model = Holidays
    message = "List of holidays"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        status_value = request_value(request, "status", "Status")
        if status_value not in (None, "", "-1"):
            queryset = queryset.filter(status=to_bool(status_value))
        return queryset


class HolidaysGetallholidaysbyteacheridGetView(ModelListView):
    """Lists holidays for the center assigned to a teacher."""
    serializer_class = api_serializers.HolidaysTeacherIdQuerySerializer
    model = Holidays
    message = "List of holidays"

    def get_queryset(self, request):
        teacher = Teacher.objects.filter(pk=request_value(request, "teacherId", "TeacherId")).first()
        return Holidays.objects.filter(center=teacher.center) if teacher and teacher.center_id else Holidays.objects.none()


class HolidaysGetallholidaysbycenteridGetView(ModelListView):
    """Lists holidays for a center."""
    serializer_class = api_serializers.HolidaysCenterIdQuerySerializer
    model = Holidays
    message = "List of holidays"

    def get_queryset(self, request):
        return Holidays.objects.filter(center_id=request_value(request, "centerId", "CenterId"))


class HolidaysGetallholidaysbyyearGetView(ModelListView):
    """Lists holidays whose start date falls in a year."""
    serializer_class = api_serializers.HolidaysYearQuerySerializer
    model = Holidays
    message = "List of holidays"

    def get_queryset(self, request):
        year = to_int(request_value(request, "year", "Year"), 0)
        return Holidays.objects.filter(start_date__year=year) if year else Holidays.objects.all()


class HolidaysDeleteholidaybyidPostView(DotNetAPIView):
    """Deletes a holiday by id."""
    serializer_class = api_serializers.HolidaysDeleteHolidayByIdQuerySerializer

    def post(self, request, *args, **kwargs):
        obj = get_by_id(Holidays, request, "holidayId", "HolidayId", "id", "Id")
        if not obj:
            return fail("Holiday not deleted")
        obj.delete()
        return ok(message="Holiday deleted")


class StudentSavestudentPostView(ModelSaveView):
    """Saves or updates student details and creates enrollment id when missing."""
    serializer_class = api_serializers.StudentSaveStudentRequestSerializer
    model = Student
    success_message = "Student save successfully"

    def post(self, request, *args, **kwargs):
        defaults = {"enrollment_id": request_value(request, "EnrollmentId", "enrollmentId") or str(uuid.uuid4())}
        obj = save_model_from_request(Student, request, defaults=defaults)
        return ok(model_payload(obj), self.success_message)


class StudentGetstudentbyidGetView(ModelDetailView):
    """Returns a student by student id."""
    serializer_class = api_serializers.StudentGetStudentByIdQuerySerializer
    model = Student
    id_names = ("studentId", "StudentId")
    found_message = "student exists"
    missing_message = "student not exists"


class StudentUpdatestudentactiveorinactivePostView(DotNetAPIView):
    """Updates a student active/inactive status."""
    serializer_class = api_serializers.StudentUpdateStudentActiveOrInactiveRequestSerializer

    def post(self, request, *args, **kwargs):
        student = get_by_id(Student, request, "studentId", "StudentId", "Id")
        if not student:
            return fail("Status not updated")
        student.status = to_bool(request_value(request, "status", "Status"))
        student.save(update_fields=["status"])
        return ok(model_payload(student), "Status updated")


class StudentGettotalstudentpresentGetView(DotNetAPIView):
    """Returns total present student attendance count for an optional date."""
    serializer_class = api_serializers.StudentGetTotalStudentPresentQuerySerializer

    def get(self, request, *args, **kwargs):
        scan_date = parse_any_datetime(request_value(request, "scanDate", "ScanDate"))
        queryset = StudentAttendance.objects.all()
        if scan_date:
            queryset = queryset.filter(scan_date__date=scan_date)
        return ok({"total": queryset.count()}, "Total count")


class StudentGetallstudentsGetView(ModelListView):
    """Lists students filtered by optional location identifiers."""
    serializer_class = api_serializers.StudentGetAllStudentsQuerySerializer
    model = Student
    message = "Total students"

    def get_queryset(self, request):
        queryset = Student.objects.all().order_by("id")
        queryset = filter_if_present(queryset, request, "district_id", "districtId", "DistrictId")
        queryset = filter_if_present(queryset, request, "vidhan_sabha_id", "vidhanSabhaId", "VidhanSabhaId")
        queryset = filter_if_present(queryset, request, "panchayat_id", "panchayatId", "PanchayatId")
        queryset = filter_if_present(queryset, request, "village_id", "villageId", "VillageId")
        return queryset


class StudentattendanceSavestudentattendancePostView(ModelSaveView):
    """Saves a student attendance record."""
    serializer_class = api_serializers.StudentAttendanceSaveRequestSerializer
    model = StudentAttendance
    success_message = "Student attendance applied"


class StudentattendanceSaveautomaticstudentattendancePostView(StudentattendanceSavestudentattendancePostView):
    """Compatibility view for automatic attendance save requests."""
    serializer_class = api_serializers.StudentAttendanceSaveRequestSerializer


class StudentattendanceSavemanualstudentattendancePostView(StudentattendanceSavestudentattendancePostView):
    """Compatibility view for manual attendance save requests."""
    serializer_class = api_serializers.StudentAttendanceSaveRequestSerializer


class StudentattendanceGetallstudentwihavgattendanceGetView(DotNetAPIView):
    """Lists center students with their average attendance value."""
    serializer_class = api_serializers.StudentAttendanceCenterQuerySerializer

    def get(self, request, *args, **kwargs):
        center_id = request_value(request, "centerId", "CenterId")
        students = Student.objects.filter(center_id=center_id).annotate(avg_attendance=Avg("attendances__type"))
        data = []
        for student in students:
            payload = model_payload(student)
            payload["avg_attendance"] = student.avg_attendance
            data.append(payload)
        return ok(data, "Students exists")


class StudentattendanceGetallabsentattendanceGetView(ModelListView):
    """Lists active students without attendance for the selected center."""
    serializer_class = api_serializers.StudentAttendanceCenterQuerySerializer
    model = Student
    message = "List of all active students exists"

    def get_queryset(self, request):
        center_id = request_value(request, "centerId", "CenterId")
        present_ids = StudentAttendance.objects.filter(center_id=center_id).values_list("student_id", flat=True)
        return Student.objects.filter(center_id=center_id, status=True).exclude(id__in=present_ids)


class StudentattendanceGetallstudentattendancstatusGetView(DotNetAPIView):
    """Lists students with present/absent status for a center and date."""
    serializer_class = api_serializers.StudentAttendanceStatusQuerySerializer

    def get(self, request, *args, **kwargs):
        center_id = request_value(request, "centerId", "CenterId")
        scan_date = parse_any_datetime(request_value(request, "scanDate", "ScanDate"))
        students = Student.objects.filter(center_id=center_id)
        data = []
        for student in students:
            attendance = StudentAttendance.objects.filter(center_id=center_id, student=student)
            if scan_date:
                attendance = attendance.filter(scan_date__date=scan_date)
            payload = model_payload(student)
            payload["is_present"] = attendance.exists()
            data.append(payload)
        return ok(data, "Student status exists")


class StudentattendanceGetallstudentattendancbymonthGetView(ModelListView):
    """Lists attendance records filtered by center, student, month, and year."""
    serializer_class = api_serializers.StudentAttendanceByMonthQuerySerializer
    model = StudentAttendance
    message = "Student exists"

    def get_queryset(self, request):
        queryset = StudentAttendance.objects.all().order_by("scan_date")
        queryset = filter_if_present(queryset, request, "center_id", "centerId", "CenterId")
        queryset = filter_if_present(queryset, request, "student_id", "studentId", "StudentId")
        month = to_int(request_value(request, "month", "Month"), 0)
        year = to_int(request_value(request, "year", "Year"), 0)
        if month:
            queryset = queryset.filter(scan_date__month=month)
        if year:
            queryset = queryset.filter(scan_date__year=year)
        return queryset


class UserSavesuperadminPostView(ModelSaveView):
    """Saves a super admin user with hashed password storage."""
    serializer_class = api_serializers.UserSaveSuperAdminRequestSerializer
    model = User
    success_message = "SuperAdmin save successfully"


class UserSaveuserPostView(ModelSaveView):
    """Saves a user record with hashed password storage."""
    serializer_class = api_serializers.UserSaveUserRequestSerializer
    model = User
    success_message = "Data save successfully"


class UserUpdatesuperadminuserPostView(UserSaveuserPostView):
    """Updates a super admin user using the same save behavior."""
    serializer_class = api_serializers.UserSaveUserRequestSerializer


class UserUpdatedeviceidPostView(DotNetAPIView):
    """Updates the stored device id for a user."""
    serializer_class = api_serializers.UserUpdateDeviceIdRequestSerializer

    def post(self, request, *args, **kwargs):
        user = get_by_id(User, request, "userId", "UserId")
        if not user:
            return fail("SuperAdmin doesn't save")
        user.device_id = request_value(request, "deviceId", "DeviceId")
        user.save(update_fields=["device_id"])
        return ok(model_payload(user), "SuperAdmin save successfully")


class UserGetuserbyidGetView(ModelDetailView):
    """Returns a user by user id."""
    serializer_class = api_serializers.UserGetUserByIdQuerySerializer
    model = User
    id_names = ("userId", "UserId")
    found_message = "user exists"
    missing_message = "user not exists"


class UserGetuserdetailbyphonenumberGetView(DotNetAPIView):
    """Returns user details for a phone number."""
    serializer_class = api_serializers.UserGetUserDetailByPhoneNumberQuerySerializer

    def get(self, request, *args, **kwargs):
        phone = request_value(request, "phoneNumer", "phoneNumber", "PhoneNumber")
        user = User.objects.filter(phone_number=phone).first()
        if user:
            return ok(model_payload(user), "user exists")
        return ok({}, "user not exists", extra={"status": False})


class UserUpdatepasswordGetView(DotNetAPIView):
    """Hashes and updates a user password."""
    serializer_class = api_serializers.UserUpdatePasswordQuerySerializer

    def get(self, request, *args, **kwargs):
        user = get_by_id(User, request, "userId", "UserId")
        if not user:
            return ok({}, "password not updated", extra={"status": False})
        user.password = hash_password(request_value(request, "newPassword", "NewPassword"))
        user.save(update_fields=["password"])
        return ok(model_payload(user), "password updated")


class UserGetallteachersGetView(ModelListView):
    """Lists teachers, optionally filtered by creator user id."""
    serializer_class = api_serializers.UserGetAllTeachersQuerySerializer
    model = Teacher
    message = "List of assigned teachers"

    def get_queryset(self, request):
        queryset = Teacher.objects.all().order_by("id")
        user_id = request_value(request, "userId", "UserId")
        if user_id not in (None, "", "0", 0):
            queryset = queryset.filter(created_by=user_id)
        return queryset


class UserGetallunassignedteacherGetView(ModelListView):
    """Lists teachers without an assigned center."""
    model = Teacher
    message = "List of teachers"

    def get_queryset(self, request):
        return Teacher.objects.filter(center__isnull=True).order_by("id")


class UserGetallregionaladminsGetView(ModelListView):
    """Lists all regional admins."""
    model = RegionalAdmin
    message = "List of regional admins"


class UserSearchdataGetView(DotNetAPIView):
    """Searches users, teachers, regional admins, or students by name/phone."""
    serializer_class = api_serializers.UserSearchDataQuerySerializer

    def get(self, request, *args, **kwargs):
        search_type = (request_value(request, "type", "Type") or "").lower()
        query = request_value(request, "queryString", "QueryString", default="")
        model = {"student": Student, "teacher": Teacher, "user": User, "regionaladmin": RegionalAdmin}.get(search_type, Student)
        name_field = "full_name" if hasattr(model, "full_name") else "name"
        queryset = model.objects.filter(Q(**{f"{name_field}__icontains": query}) | Q(phone_number__icontains=query))[:25]
        return ok(queryset_payload(queryset), "List of search data")


class TeacherLoginteacherPostView(DotNetAPIView):
    """Authenticates a teacher using SHA-256 hashed password comparison."""
    serializer_class = api_serializers.LoginRequestSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        mobile = request_value(request, "mobileNumber", "MobileNumber")
        password = hash_password(request_value(request, "password", "Password"))
        teacher = Teacher.objects.filter(phone_number=mobile, password=password).first()
        if teacher:
            return login_response(teacher, "teacher", mobile)
        return fail("invalid credential", code=status.HTTP_404_NOT_FOUND)


class TeacherSaveteacherPostView(ModelSaveView):
    """Saves a teacher record with hashed password storage."""
    serializer_class = api_serializers.TeacherSaveTeacherRequestSerializer
    model = Teacher
    guid_field = "teacher_guid_id"
    success_message = "Teacher save successfully"


class RegionaladminGetallregionaladminGetView(ModelListView):
    """Lists all regional admin records."""
    model = RegionalAdmin
    message = "List of regional admins"


class RegionaladminLoginregionaladminPostView(DotNetAPIView):
    """Authenticates a regional admin using hashed password comparison."""
    serializer_class = api_serializers.LoginRequestSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        mobile = request_value(request, "mobileNumber", "MobileNumber")
        password = hash_password(request_value(request, "password", "Password"))
        admin = RegionalAdmin.objects.filter(phone_number=mobile, password=password).first()
        if admin:
            return login_response(admin, "regional_admin", mobile)
        return fail("invalid credential", code=status.HTTP_404_NOT_FOUND)


class RegionaladminSaveregionaladminPostView(ModelSaveView):
    """Saves a regional admin record with hashed password storage."""
    serializer_class = api_serializers.RegionalAdminSaveRegionalAdminRequestSerializer
    model = RegionalAdmin
    guid_field = "regional_admin_guid_id"
    success_message = "RegionalAdmin save successfully"


class FileSendnotificationPostView(DotNetAPIView):
    """Accepts notification send requests as a compatibility endpoint."""
    serializer_class = api_serializers.FileSendNotificationRequestSerializer

    def post(self, request, *args, **kwargs):
        return ok(message="Notification request accepted")


class FileUploadprofileimagePostView(DotNetAPIView):
    """Stores uploaded profile image files and returns their URLs."""
    serializer_class = api_serializers.FileUploadProfileImageRequestSerializer

    def post(self, request, *args, **kwargs):
        uploaded = []
        for file_obj in request.FILES.getlist("files") or request.FILES.values():
            file_name = default_storage.save(f"UploadProfileImage/{uuid.uuid4()}_{file_obj.name}", file_obj)
            uploaded.append(default_storage.url(file_name))
        return ok(uploaded, "File uploaded successfully")


class DashboardGetclasscountbymonthGetView(DotNetAPIView):
    """Returns class counts grouped by started month."""
    serializer_class = api_serializers.DashboardCenterDateRangeQuerySerializer

    def get(self, request, *args, **kwargs):
        queryset = ClassModel.objects.all()
        queryset = filter_if_present(queryset, request, "center_id", "centerId", "CenterId")
        data = queryset.values("started_date__month").annotate(total=Count("id")).order_by("started_date__month")
        return ok(list(data), "Class count")


class DashboardGettotalgenterratiobycenteridGetView(DotNetAPIView):
    """Returns student gender counts for a center."""
    serializer_class = api_serializers.DashboardCenterDateRangeQuerySerializer

    def get(self, request, *args, **kwargs):
        queryset = Student.objects.all()
        queryset = filter_if_present(queryset, request, "center_id", "centerId", "CenterId")
        return ok(list(queryset.values("gender").annotate(total=Count("id"))), "Gender ratio")


class DashboardGettotalstudentofclassGetView(DotNetAPIView):
    """Returns total students for a center."""
    serializer_class = api_serializers.DashboardCenterDateRangeQuerySerializer

    def get(self, request, *args, **kwargs):
        center_id = request_value(request, "centerId", "CenterId")
        return ok({"total": Student.objects.filter(center_id=center_id).count()}, "Total students")


class DashboardGetcenterdetailbymonthGetView(DotNetAPIView):
    """Returns center details with class and student counts."""
    serializer_class = api_serializers.DashboardGetCenterDetailByMonthQuerySerializer

    def get(self, request, *args, **kwargs):
        center = get_by_id(Center, request, "centerId", "CenterId")
        data = model_payload(center) if center else {}
        if center:
            data["class_count"] = ClassModel.objects.filter(center=center).count()
            data["student_count"] = Student.objects.filter(center=center).count()
        return ok(data, "Center detail")


class DashboardGettotalbplGetView(DotNetAPIView):
    """Returns total BPL students for optional center filter."""
    serializer_class = api_serializers.DashboardCenterDateRangeQuerySerializer

    def get(self, request, *args, **kwargs):
        queryset = Student.objects.filter(bpl=True)
        queryset = filter_if_present(queryset, request, "center_id", "centerId", "CenterId")
        return ok({"total": queryset.count()}, "Total BPL")


class DashboardGettotalstudentcategoryofclassGetView(DotNetAPIView):
    """Returns student category counts for optional center filter."""
    serializer_class = api_serializers.DashboardCenterDateRangeQuerySerializer

    def get(self, request, *args, **kwargs):
        queryset = Student.objects.all()
        queryset = filter_if_present(queryset, request, "center_id", "centerId", "CenterId")
        return ok(list(queryset.values("category").annotate(total=Count("id"))), "Student category")


class DashboardGetuserbyfilterGetView(ModelListView):
    """Lists students matching dashboard location filters."""
    serializer_class = api_serializers.DashboardFilterQuerySerializer
    model = Student
    message = "Users by filter"

    def get_queryset(self, request):
        queryset = Student.objects.all()
        queryset = filter_if_present(queryset, request, "district_id", "districtId", "DistrictId")
        queryset = filter_if_present(queryset, request, "vidhan_sabha_id", "vidhanSabhaId", "VidhanSabhaId")
        queryset = filter_if_present(queryset, request, "panchayat_id", "panchaytaId", "panchayatId", "PanchayatId")
        queryset = filter_if_present(queryset, request, "village_id", "villageId", "VillageId")
        return queryset


class DashboardGettotalbplbyfilterGetView(DashboardGetuserbyfilterGetView):
    """Returns BPL count for dashboard location filters."""
    serializer_class = api_serializers.DashboardFilterQuerySerializer

    def get(self, request, *args, **kwargs):
        return ok({"total": self.get_queryset(request).filter(bpl=True).count()}, "Total BPL")


class DashboardGettotalgenderratiobyfilterGetView(DashboardGetuserbyfilterGetView):
    """Returns gender counts for dashboard location filters."""
    serializer_class = api_serializers.DashboardFilterQuerySerializer

    def get(self, request, *args, **kwargs):
        return ok(list(self.get_queryset(request).values("gender").annotate(total=Count("id"))), "Gender ratio")


class DashboardGettotalstudentcategoryofclassbyfilterGetView(DashboardGetuserbyfilterGetView):
    """Returns category counts for dashboard location filters."""
    serializer_class = api_serializers.DashboardFilterQuerySerializer

    def get(self, request, *args, **kwargs):
        return ok(list(self.get_queryset(request).values("category").annotate(total=Count("id"))), "Student category")


class DashboardGettotalstudengradeofclassbyfilterGetView(DashboardGetuserbyfilterGetView):
    """Returns grade counts for dashboard location filters."""
    serializer_class = api_serializers.DashboardFilterQuerySerializer

    def get(self, request, *args, **kwargs):
        return ok(list(self.get_queryset(request).values("grade").annotate(total=Count("id"))), "Student grade")


class DashboardGetdistrictofcenterbyfilterGetView(ModelListView):
    """Lists centers matching district and Vidhan Sabha dashboard filters."""
    serializer_class = api_serializers.DashboardDistrictOfCenterByFilterQuerySerializer
    model = Center
    message = "District of center"

    def get_queryset(self, request):
        queryset = Center.objects.all()
        queryset = filter_if_present(queryset, request, "district_id", "districtId", "DistrictId")
        queryset = filter_if_present(queryset, request, "vidhan_sabha_id", "vidhanSabhaId", "VidhanSabhaId")
        return queryset


class DashboardGetstudentattendancebypercentageGetView(DotNetAPIView):
    """Returns overall attendance percentage across students."""
    def get(self, request, *args, **kwargs):
        total_students = Student.objects.count()
        present = StudentAttendance.objects.values("student_id").distinct().count()
        percentage = (present / total_students * 100) if total_students else 0
        return ok({"percentage": percentage, "present": present, "totalStudents": total_students}, "Attendance percentage")


class WeatherforecastGetView(DotNetAPIView):
    """Keeps the default .NET WeatherForecast sample route available."""
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return Response(
            [
                {
                    "date": now().date(),
                    "temperatureC": 25,
                    "temperatureF": 76,
                    "summary": "Warm",
                }
            ],
            status=status.HTTP_200_OK,
        )
