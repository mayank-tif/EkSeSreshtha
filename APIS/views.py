from datetime import timedelta
import re
import uuid
from django.forms.models import model_to_dict
from django.db.models import Avg, Count, Q
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView
from EkSeSreshtha.env_details import *
from .models import *
from .serializers import GenerateAppTokenSerializer, LoginSerializer
from .utils import *
from django.utils.timezone import now


SUPER_ADMIN = 1
REGIONAL_ADMIN = 2
TEACHER = 3

ADMIN_ROLES = [SUPER_ADMIN, REGIONAL_ADMIN]
ALL_USER_ROLES = [SUPER_ADMIN, REGIONAL_ADMIN, TEACHER]


class DummyUser:
    def __init__(self, username):
        self.username = username
        self.id = 1


@method_decorator(csrf_exempt, name='dispatch')
class GenerateAppTokenView(TokenObtainPairView):
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


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        validate_app_and_device_with_token(request)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        mobile_number = serializer.validated_data["mobile_number"]
        password = serializer.validated_data["password"]

        account = None
        account_type = None

        user = User.objects.filter(phone_number=mobile_number, password=password).first()
        if user:
            account = user
            account_type = "super_admin"
        else:
            teacher = Teacher.objects.filter(phone_number=mobile_number, password=password).first()
            if teacher:
                account = teacher
                account_type = "teacher"
            else:
                regional_admin = RegionalAdmin.objects.filter(phone_number=mobile_number, password=password).first()
                if regional_admin:
                    account = regional_admin
                    account_type = "regional_admin"

        if not account:
            return Response({"detail": "Invalid mobile number or password."}, status=status.HTTP_401_UNAUTHORIZED)

        token = AccessToken()
        token["user_id"] = account.id
        token["user_type"] = account_type
        token["mobile_number"] = mobile_number
        token["name"] = getattr(account, "full_name", None) or getattr(account, "name", None) or mobile_number
        token.set_exp(lifetime=timedelta(days=1))

        account.last_login_time = now().strftime("%Y-%m-%d %H:%M:%S")
        account.token = str(token)
        account.save(update_fields=["last_login_time", "token"])

        payload = model_to_dict(account, exclude=["password", "token"])
        payload["user_type"] = account_type

        return Response(
            {
                "access_token": str(token),
                "user_type": account_type,
                "user": payload,
            },
            status=status.HTTP_200_OK,
        )

class BaseAPIView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    allowed_roles = []


def success_response(data=None, message="Success", status_code=status.HTTP_200_OK):
    return Response({"message": message, "data": data}, status=status_code)


def not_found_response(message="Data not found."):
    return Response({"message": message, "data": None}, status=status.HTTP_404_NOT_FOUND)


def bad_request_response(message):
    return Response({"message": message, "data": None}, status=status.HTTP_400_BAD_REQUEST)


def request_data(request):
    data = request.data.copy()
    for key in request.FILES.keys():
        files = request.FILES.getlist(key)
        value = files if len(files) > 1 else files[0]
        if hasattr(data, "setlist") and isinstance(value, list):
            data.setlist(key, value)
        else:
            data[key] = value
    return data


def request_param(request, *names, default=None):
    for name in names:
        value = request.query_params.get(name)
        if value not in (None, ""):
            return value
    return default


def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    if str(value).lower() in {"1", "true", "active", "yes"}:
        return True
    if str(value).lower() in {"0", "false", "inactive", "no"}:
        return False
    return None


def parse_date_value(value):
    if not value:
        return None
    return parse_date(str(value)) or (parse_datetime(str(value)).date() if parse_datetime(str(value)) else None)


def serialize_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def serialize_instance(instance):
    data = {}
    for field in instance._meta.fields:
        if field.is_relation and getattr(field, "many_to_one", False):
            data[field.db_column or f"{field.name}_id"] = getattr(instance, field.attname)
        else:
            data[field.db_column or field.name] = serialize_value(getattr(instance, field.name))
    return data


def serialize_queryset(queryset):
    return [serialize_instance(instance) for instance in queryset]


def paginate_queryset(queryset, request):
    offset = to_int(request_param(request, "offset"), 0) or 0
    limit = to_int(request_param(request, "limit"), 0) or 0
    if limit > 0:
        return queryset[offset:offset + limit]
    if offset > 0:
        return queryset[offset:]
    return queryset


def normalize_name(value):
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return value.replace("-", "_").lower()


def field_lookup(model):
    mapping = {}
    for field in model._meta.fields:
        names = {field.name, normalize_name(field.name)}
        if field.db_column:
            names.add(field.db_column)
            names.add(normalize_name(field.db_column))
        if field.is_relation and getattr(field, "many_to_one", False):
            names.add(field.attname)
            if field.db_column:
                names.add(f"{field.db_column}_id")
        for name in names:
            mapping[str(name).lower()] = field
    return mapping


def file_value(value):
    if isinstance(value, list):
        return ",".join(getattr(item, "name", str(item)) for item in value)
    return getattr(value, "name", value)


def assign_model_fields(instance, data):
    lookup = field_lookup(instance.__class__)
    for key, value in data.items():
        if key in {"csrfmiddlewaretoken"} or value in (None, ""):
            continue
        field = lookup.get(str(key).lower()) or lookup.get(normalize_name(str(key)))
        if not field or getattr(field, "primary_key", False):
            continue
        value = file_value(value)
        if field.is_relation and getattr(field, "many_to_one", False):
            setattr(instance, field.attname, to_int(value))
        else:
            setattr(instance, field.name, value)


def ensure_guid(instance):
    for field in instance._meta.fields:
        if "guid" in field.name and not getattr(instance, field.name):
            setattr(instance, field.name, str(uuid.uuid4()))


def save_model_instance(model, request, defaults=None):
    data = request_data(request)
    record_id = to_int(data.get("Id") or data.get("id"))
    instance = model.objects.filter(id=record_id).first() if record_id else model()
    created = instance.pk is None
    assign_model_fields(instance, data)
    ensure_guid(instance)
    if hasattr(instance, "created_on") and not instance.created_on:
        instance.created_on = now()
    if hasattr(instance, "created_by") and not instance.created_by:
        instance.created_by = to_int(data.get("CreatedBy") or data.get("createdBy"))
    if defaults:
        for key, value in defaults.items():
            setattr(instance, key, value)
    instance.save()
    return success_response(serialize_instance(instance), "Saved successfully" if created else "Updated successfully")


def get_model_by_id(model, record_id):
    if not record_id:
        return bad_request_response("Id is required.")
    instance = model.objects.filter(id=record_id).first()
    if not instance:
        return not_found_response()
    return success_response(serialize_instance(instance))


def list_model(model, request, queryset=None):
    queryset = queryset if queryset is not None else model.objects.all()
    queryset = paginate_queryset(queryset.order_by("id"), request)
    return success_response(serialize_queryset(queryset))


def check_name_exists(model, request):
    name = request_param(request, "name") or request.data.get("name") or request.data.get("Name")
    if not name:
        return bad_request_response("name is required.")
    field_name = "name" if hasattr(model, "name") else "school_name"
    return success_response({"exists": model.objects.filter(**{f"{field_name}__iexact": name}).exists()})


def model_count(queryset):
    return success_response({"count": queryset.count()})


def filter_by_status(queryset, request):
    status_value = request_param(request, "status")
    bool_status = to_bool(status_value)
    if bool_status is not None:
        queryset = queryset.filter(status=bool_status)
    return queryset


def filter_by_location(queryset, request):
    for param, field in [
        ("districtId", "district_id"),
        ("vidhanSabhaId", "vidhan_sabha_id"),
        ("panchayatId", "panchayat_id"),
        ("villageId", "village_id"),
        ("centerId", "center_id"),
    ]:
        value = to_int(request_param(request, param))
        if value and hasattr(queryset.model, field):
            queryset = queryset.filter(**{field: value})
    return queryset


def attendance_queryset(request):
    queryset = StudentAttendance.objects.all()
    center_id = to_int(request_param(request, "centerId"))
    user_id = to_int(request_param(request, "userId", "teacherId"))
    class_id = to_int(request_param(request, "classId"))
    date_value = parse_date_value(request_param(request, "date"))
    if center_id:
        queryset = queryset.filter(center_id=center_id)
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    if class_id:
        queryset = queryset.filter(class_obj_id=class_id)
    if date_value:
        queryset = queryset.filter(scan_date__date=date_value)
    return queryset


def save_user_by_role(request, role_id=None, model=User):
    defaults = {"role_id": role_id, "type": role_id} if role_id else None
    return save_model_instance(model, request, defaults=defaults)


def search_users(request):
    query = request_param(request, "queryString", default="")
    user_type = request_param(request, "type")
    queryset = User.objects.all()
    if user_type:
        queryset = queryset.filter(type=to_int(user_type))
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(email__icontains=query)
        )
    return list_model(User, request, queryset)

class AnnouncementSaveannouncementPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(Announcement, request)


class AnnouncementGetannouncementGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Announcement, request)


class CenterSavecenterPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(Center, request)


class CenterGetcenteryidGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return get_model_by_id(Center, to_int(request_param(request, "centeId", "centerId", "id")))


class CenterGetallcentersGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = Center.objects.all()
        user_id = to_int(request_param(request, "userId"))
        user_type = to_int(request_param(request, "type"))
        if user_id and user_type == REGIONAL_ADMIN:
            queryset = queryset.filter(assigned_regional_admin=user_id)
        elif user_id and user_type == TEACHER:
            queryset = queryset.filter(assigned_teachers=user_id)
        return list_model(Center, request, queryset)


class CenterGetallcentersbystatusGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = filter_by_status(Center.objects.all(), request)
        return list_model(Center, request, queryset)


class CenterGetcenterbyteacheridGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        user_id = to_int(request_param(request, "userId"))
        queryset = Center.objects.filter(Q(assigned_teachers=user_id) | Q(teachers__id=user_id)).distinct() if user_id else Center.objects.none()
        return list_model(Center, request, queryset)


class CenterGetallcenterattendanceGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = attendance_queryset(request).values("center_id").annotate(total=Count("id")).order_by("center_id")
        return success_response(list(queryset))


class CenterUpdatecenteractiveordeactiveGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        center_id = to_int(request.data.get("centerId") or request.data.get("CenterId"))
        if not center_id:
            return bad_request_response("centerId is required.")
        center = Center.objects.filter(id=center_id).first()
        if not center:
            return not_found_response("Center not found.")
        new_status = to_bool(request.data.get("status") if "status" in request.data else request.data.get("Status"))
        if new_status is not None:
            center.status = new_status
            center.save(update_fields=["status"])
        save_model_instance(CenterLog, request)
        return success_response(serialize_instance(center), "Center status updated")


class CenterGettotalattendancecountofcenterGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return model_count(attendance_queryset(request))


class ClassSaveclassPostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(ClassModel, request)


class ClassCancelclassPostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        class_id = to_int(request.data.get("Id") or request.data.get("id"))
        instance = ClassModel.objects.filter(id=class_id).first()
        if not instance:
            return not_found_response("Class not found.")
        instance.reason = request.data.get("Reason") or request.data.get("reason")
        instance.cancel_by = to_int(request.data.get("CancelBy") or request.data.get("cancelBy"))
        instance.cancel_date = now()
        instance.status = 0
        instance.save()
        return success_response(serialize_instance(instance), "Class cancelled")


class ClassUpdateendclasstimePostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        instance = ClassModel.objects.filter(id=to_int(request.data.get("Id") or request.data.get("id"))).first()
        if not instance:
            return not_found_response("Class not found.")
        instance.end_date = now()
        instance.save(update_fields=["end_date"])
        return success_response(serialize_instance(instance), "Class end time updated")


class ClassUpdateclasssubstatusPostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        instance = ClassModel.objects.filter(id=to_int(request.data.get("Id") or request.data.get("id"))).first()
        if not instance:
            return not_found_response("Class not found.")
        instance.sub_status = 1 if not instance.sub_status else 0
        instance.save(update_fields=["sub_status"])
        return success_response(serialize_instance(instance), "Class sub status updated")


class ClassCancelclassbyteacherPostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(ClassCancelByTeacher, request)


class ClassDeleteclassbyteacheridPostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        class_id = to_int(request_param(request, "classId") or request.data.get("classId"))
        instance = ClassModel.objects.filter(id=class_id).first()
        if not instance:
            return not_found_response("Class not found.")
        instance.delete()
        return success_response({"id": class_id}, "Class deleted")


class ClassGetclasscurrentstatusGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        center_id = to_int(request_param(request, "centerId"))
        teacher_id = to_int(request_param(request, "teacherId"))
        queryset = ClassModel.objects.all()
        if center_id:
            queryset = queryset.filter(center_id=center_id)
        if teacher_id:
            queryset = queryset.filter(users_id=teacher_id)
        instance = queryset.order_by("-started_date", "-id").first()
        return success_response(serialize_instance(instance) if instance else None)


class ClassGetliveclassdetailGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        class_id = to_int(request_param(request, "classId"))
        queryset = ClassDetail.objects.filter(class_obj_id=class_id) if class_id else ClassDetail.objects.none()
        return list_model(ClassDetail, request, queryset)


class DashboardGetclasscountbymonthGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = filter_by_location(ClassModel.objects.all(), request)
        return success_response({"count": queryset.count()})


class DashboardGettotalgenterratiobycenteridGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = filter_by_location(Student.objects.all(), request).values("gender").annotate(total=Count("id"))
        return success_response(list(queryset))


class DashboardGettotalstudentofclassGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return model_count(filter_by_location(Student.objects.all(), request))


class DashboardGetcenterdetailbymonthGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Center, request, filter_by_location(Center.objects.all(), request))


class DashboardGettotalbplGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return model_count(Student.objects.filter(bpl=True))


class DashboardGettotalstudentcategoryofclassGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = filter_by_location(Student.objects.all(), request).values("category").annotate(total=Count("id"))
        return success_response(list(queryset))


class DashboardGetuserbyfilterGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return search_users(request)


class DashboardGettotalbplbyfilterGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return model_count(filter_by_location(Student.objects.filter(bpl=True), request))


class DashboardGettotalgenderratiobyfilterGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = filter_by_location(Student.objects.all(), request).values("gender").annotate(total=Count("id"))
        return success_response(list(queryset))


class DashboardGettotalstudentcategoryofclassbyfilterGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = filter_by_location(Student.objects.all(), request).values("category").annotate(total=Count("id"))
        return success_response(list(queryset))


class DashboardGettotalstudengradeofclassbyfilterGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = filter_by_location(Student.objects.all(), request).values("grade").annotate(total=Count("id"))
        return success_response(list(queryset))


class DashboardGetdistrictofcenterbyfilterGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        queryset = Center.objects.values("district_id").annotate(total=Count("id"))
        return success_response(list(queryset))


class DashboardGetstudentattendancebypercentageGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        total = Student.objects.count()
        present = attendance_queryset(request).values("student_id").distinct().count()
        percentage = (present * 100 / total) if total else 0
        return success_response({"totalStudents": total, "presentStudents": present, "percentage": percentage})


class DistrictGetalldistrictGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(District, request)


class DistrictSavedistrictPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(District, request)


class FileSendnotificationPostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        return success_response({"sent": True}, "Notification accepted")


class FileUploadprofileimagePostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        data = request_data(request)
        return success_response({"file": file_value(data.get("ImageFile") or data.get("file") or data.get("Picture"))}, "File uploaded")


class HolidaysSaveholidaysPostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(Holidays, request)


class HolidaysGetallholidaysbyteacheridGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        teacher_id = to_int(request_param(request, "teacherId", "userId"))
        centers = Teacher.objects.filter(id=teacher_id).values_list("center_id", flat=True) if teacher_id else []
        queryset = Holidays.objects.filter(center_id__in=centers) if teacher_id else Holidays.objects.all()
        return list_model(Holidays, request, queryset)


class HolidaysGetallholidaysbycenteridGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        center_id = to_int(request_param(request, "centerId"))
        queryset = Holidays.objects.filter(center_id=center_id) if center_id else Holidays.objects.all()
        return list_model(Holidays, request, queryset)


class HolidaysGetallholidaysbyyearGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        year = to_int(request_param(request, "year"))
        queryset = Holidays.objects.filter(start_date__year=year) if year else Holidays.objects.all()
        return list_model(Holidays, request, queryset)


class HolidaysGetallholidaysGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Holidays, request)


class HolidaysDeleteholidaybyidPostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        holiday_id = to_int(request_param(request, "holidayId", "id") or request.data.get("Id"))
        instance = Holidays.objects.filter(id=holiday_id).first()
        if not instance:
            return not_found_response("Holiday not found.")
        instance.delete()
        return success_response({"id": holiday_id}, "Holiday deleted")


class PanchayatGetallpanchayatGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Panchayat, request)


class PanchayatSavepanchayatPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(Panchayat, request)


class PanchayatGetpanchayatbydistrictandvidhansabhaidGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Panchayat, request, filter_by_location(Panchayat.objects.all(), request))


class PanchayatCheckpanchayatnamePostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return check_name_exists(Panchayat, request)


class SchoolSaveschoolPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(School, request)


class SchoolGetallschoolsGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(School, request)


class StudentSavestudentPostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(Student, request)


class StudentGetstudentbyidGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        return get_model_by_id(Student, to_int(request_param(request, "studentId", "id")))


class StudentUpdatestudentactiveorinactivePostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        student_id = to_int(request_param(request, "studentId", "id") or request.data.get("StudentId") or request.data.get("Id"))
        instance = Student.objects.filter(id=student_id).first()
        if not instance:
            return not_found_response("Student not found.")
        status_value = to_bool(request_param(request, "status") or request.data.get("Status"))
        instance.status = status_value if status_value is not None else not bool(instance.status)
        instance.save(update_fields=["status"])
        return success_response(serialize_instance(instance), "Student status updated")


class StudentGettotalstudentpresentGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        return success_response({"count": attendance_queryset(request).values("student_id").distinct().count()})


class StudentGetallstudentsGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Student, request, filter_by_location(Student.objects.all(), request))


class StudentattendanceSavestudentattendancePostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(StudentAttendance, request)


class StudentattendanceSaveautomaticstudentattendancePostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(StudentAttendance, request)


class StudentattendanceSavemanualstudentattendancePostView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(StudentAttendance, request)


class StudentattendanceGetallstudentwihavgattendanceGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        queryset = StudentAttendance.objects.values("student_id").annotate(total=Count("id"))
        return success_response(list(queryset))


class StudentattendanceGetallabsentattendanceGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        attended = attendance_queryset(request).values_list("student_id", flat=True)
        return list_model(Student, request, Student.objects.exclude(id__in=attended))


class StudentattendanceGetallstudentattendancstatusGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(StudentAttendance, request, attendance_queryset(request))


class StudentattendanceGetallstudentattendancbymonthGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        month = to_int(request_param(request, "month"))
        year = to_int(request_param(request, "year"))
        queryset = StudentAttendance.objects.all()
        if month:
            queryset = queryset.filter(scan_date__month=month)
        if year:
            queryset = queryset.filter(scan_date__year=year)
        return list_model(StudentAttendance, request, queryset)


class UserSavesuperadminPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_user_by_role(request, SUPER_ADMIN, User)


class UserUpdatedeviceidPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        user_id = to_int(request.data.get("UserId") or request.data.get("userId"))
        instance = User.objects.filter(id=user_id).first()
        if not instance:
            return not_found_response("User not found.")
        instance.device_id = request.data.get("DeviceId") or request.data.get("deviceId")
        instance.save(update_fields=["device_id"])
        return success_response(serialize_instance(instance), "Device updated")


class UserSaveuserPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(User, request)


class UserUpdatesuperadminuserPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_user_by_role(request, SUPER_ADMIN, User)


class UserGetuserbyidGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return get_model_by_id(User, to_int(request_param(request, "userId", "id")))


class UserGetuserdetailbyphonenumberGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        phone = request_param(request, "phoneNumer", "phoneNumber")
        instance = User.objects.filter(phone_number=phone).first() or Teacher.objects.filter(phone_number=phone).first() or RegionalAdmin.objects.filter(phone_number=phone).first()
        return success_response(serialize_instance(instance) if instance else None)


class UserUpdatepasswordGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        user_id = to_int(request_param(request, "userId"))
        password = request_param(request, "newPassword")
        instance = User.objects.filter(id=user_id).first()
        if not instance:
            return not_found_response("User not found.")
        instance.password = password
        instance.save(update_fields=["password"])
        return success_response({"id": user_id}, "Password updated")


class UserGetallteachersGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Teacher, request)


class UserGetallunassignedteacherGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Teacher, request, Teacher.objects.filter(center_id__isnull=True))


class UserGetallregionaladminsGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(RegionalAdmin, request)


class UserSearchdataGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return search_users(request)


class VidhansabhaGetallvidhansabhaGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(VidhanSabha, request)


class VidhansabhaSavevidhansabhaPostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(VidhanSabha, request)


class VidhansabhaGetvidhansabhabydistrictidGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        district_id = to_int(request_param(request, "districtId"))
        queryset = VidhanSabha.objects.filter(district_id=district_id) if district_id else VidhanSabha.objects.all()
        return list_model(VidhanSabha, request, queryset)


class VidhansabhaCheckvidhansabhanamePostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return check_name_exists(VidhanSabha, request)


class VillageGetallvillageGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Village, request)


class VillageSavevillagePostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return save_model_instance(Village, request)


class VillageGetvillagebydistrictvidhansabhaandpanchidGetView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def get(self, request, *args, **kwargs):
        return list_model(Village, request, filter_by_location(Village.objects.all(), request))


class VillageCheckvillagenamePostView(BaseAPIView):
    allowed_roles = ADMIN_ROLES

    def post(self, request, *args, **kwargs):
        return check_name_exists(Village, request)


class WeatherforecastGetView(BaseAPIView):
    allowed_roles = ALL_USER_ROLES

    def get(self, request, *args, **kwargs):
        return success_response([])

