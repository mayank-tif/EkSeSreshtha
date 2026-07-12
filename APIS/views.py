import hashlib
import logging
import uuid
from datetime import timedelta

from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import Coalesce
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
from .utils import *
from .token_validation import *
from .helper import *


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


# class LoginAPIView(DotNetAPIView):
#     """Authenticates a user, teacher, or regional admin using the hashed password flow."""
#     permission_classes = [AllowAny]
#     authentication_classes = []
#     serializer_class = LoginSerializer

#     def post(self, request, *args, **kwargs):
#         logger.info("LoginAPIView started")
#         validate_app_and_device_with_token(request)
#         serializer = self.serializer_class(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         mobile_number = serializer.validated_data["mobileNumber"]
#         password = hash_password(serializer.validated_data["password"])
#         logger.info("Attempting login for mobile number: %s", mobile_number, password)

#         account = User.objects.filter(phone_number=mobile_number, password=password).first()
#         if account:
#             return login_response(account, "super_admin", mobile_number)
#         account = Teacher.objects.filter(phone_number=mobile_number, password=password).first()
#         if account:
#             return login_response(account, "teacher", mobile_number)
#         account = RegionalAdmin.objects.filter(phone_number=mobile_number, password=password).first()
#         if account:
#             return login_response(account, "regional_admin", mobile_number)
#         return fail("invalid credential", code=status.HTTP_404_NOT_FOUND)


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



class CenterGetAllCentersView(APIView):
    """Lists centers, optionally narrowing the result to a teacher/user."""
    
    def get(self, request):
        try:
            logger.info("CenterGetAllCentersView : GetAllCenters : Started")
            
            # Validate request parameters
            serializer =api_serializers.CenterGetAllCentersQuerySerializer(data=request.query_params)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            userId = serializer.validated_data.get('userId', 0)
            type_param = serializer.validated_data.get('type', 0)
            
            # Get centers
            all_centers = get_all_centers(userId, type_param)
            
            if all_centers is not None and len(all_centers) > 0:
                # Serialize response
                response_serializer = api_serializers.AllCenterDtoSerializer(all_centers, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "List of centers",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "List of centers not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"CenterGetAllCentersView : GetAllCenters : {str(e)}")
            return Response(
                {
                    "status": False,
                    "data": None,
                    "message": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class CenterGetAllCentersByStatusView(APIView):
    """Get student attendance of centers based on status and user"""

    def get(self, request):
        try:
            # Validate request parameters
            serializer = api_serializers.CenterGetAllCentersByStatusQuerySerializer(data=request.query_params)
            if not serializer.is_valid():
                return Response(
                    {"error": "Invalid parameters", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            status_param = serializer.validated_data['status']
            user_id = serializer.validated_data['userId']

            logger.info(f"CenterGetAllCentersByStatusView : GetStudentAttendanceOfCenter : Started")

            # Get user type
            user_type = get_user_type(user_id)

            TODAY = datetime.now().date()
            all_centers = []
            
            print(f"User ID: {user_id}, User Type: {user_type}, Status Param: {status_param}, Today: {TODAY}")

            # Admin user (Type == 1)
            if user_type and user_type == 1:
                all_centers = get_centers_for_admin(status_param, TODAY)
            else:
                # Regional admin
                all_centers = get_centers_for_regional_admin(status_param, user_id, TODAY)

            # Serialize response
            response_serializer = api_serializers.AllCenterStatusDtoSerializer(all_centers, many=True)

            logger.info(f"CenterGetAllCentersByStatusView : GetStudentAttendanceOfCenter : End")
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"CenterGetAllCentersByStatusView : GetStudentAttendanceOfCenter : {str(e)}")
            return Response(
                {"error": "An error occurred while processing your request"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
        data = self.validated_request_data
        class_id = data.get("Id")
        if class_id:
            obj = ClassModel.objects.filter(pk=class_id).first()
            if not obj:
                return fail("Class not found", code=status.HTTP_404_NOT_FOUND)
            obj.name = data["Name"]
            obj.center_id = data["CenterId"]
            obj.users_id = data["UserId"]
            obj.total_students = data["TotalStudents"]
            obj.avilable_students = data["AvilableStudents"]
            obj.save()
        else:
            enrollment_id = data.get("ClassEnrolmentId") or str(uuid.uuid4())
            # DAL allows one class per enrolment id, center, and day.
            if ClassModel.objects.filter(class_enrolment_id=enrollment_id, center_id=data["CenterId"], started_date__date=now().date()).exists():
                return fail("Class already exists", code=status.HTTP_409_CONFLICT)
            obj = ClassModel.objects.create(
                class_enrolment_id=enrollment_id,
                name=data["Name"], center_id=data["CenterId"], users_id=data["UserId"],
                total_students=data["TotalStudents"], avilable_students=data["AvilableStudents"],
                started_date=now(), status=1, sub_status=0,
            )
        Center.objects.filter(pk=obj.center_id).update(class_status=True)
        return ok(model_payload(obj), self.success_message)


class ClassCancelclassPostView(DotNetAPIView):
    """Cancels a class by setting status, reason, cancel user, and cancel date."""
    serializer_class = api_serializers.ClassCancelClassRequestSerializer

    def post(self, request, *args, **kwargs):
        class_id = request_value(request, "classId", "ClassId", "id", "Id")
        obj = ClassModel.objects.filter(pk=class_id).first()
        if not obj:
            return fail("Class not canceled")
        obj.status = 3
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
        obj.end_date = now()
        obj.status = 2
        obj.save(update_fields=["end_date", "status"])
        # The DAL clears ActiveClassStatus for students that attended the
        # centre when the class is completed.
        attended_student_ids = StudentAttendance.objects.filter(center_id=obj.center_id).values_list("student_id", flat=True)
        Student.objects.filter(center_id=obj.center_id, id__in=attended_student_ids).update(active_class_status=False)
        return ok(message="Time updated")


class ClassUpdateclasssubstatusPostView(DotNetAPIView):
    """Updates the class sub-status value."""
    serializer_class = api_serializers.ClassUpdateClassSubStatusRequestSerializer

    def post(self, request, *args, **kwargs):
        obj = get_by_id(ClassModel, request, "classId", "ClassId")
        if not obj:
            return fail("Status not updated")
        obj.sub_status = 1
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
        with transaction.atomic():
            ClassCancelByTeacher.objects.filter(user_id=obj.users_id).delete()
            StudentAttendance.objects.filter(class_obj=obj).delete()
            obj.delete()
        return ok(message="class deleted")


class ClassGetclasscurrentstatusGetView(DotNetAPIView):
    """Returns currently open classes for a center and optional teacher."""
    serializer_class = api_serializers.ClassGetClassCurrentStatusQuerySerializer

    def get(self, request, *args, **kwargs):
        center_id = request_value(request, "centerId", "CenterId")
        teacher_id = request_value(request, "teacherId", "TeacherId")
        today = now().date()
        data = []
        holiday = Holidays.objects.filter(center_id=center_id, start_date__date__lte=today, end_date__date__gte=today).first()
        if holiday:
            data.append({"name": holiday.name, "type": 1, "startedDate": holiday.start_date, "endDate": holiday.end_date})
        cancelled = ClassCancelByTeacher.objects.filter(user_id=teacher_id, starting_date__date__lte=today, ending_date__date__gte=today).first()
        if cancelled:
            data.append({"name": cancelled.reason, "type": 2, "startedDate": cancelled.starting_date, "endDate": cancelled.ending_date})
        active = ClassModel.objects.filter(center_id=center_id, started_date__date=today, status=1).first()
        if active:
            data.append({"name": "Class is going on", "type": 3, "subStatus": active.sub_status, "id": active.id, "startedDate": active.started_date, "endDate": active.end_date})
        completed = ClassModel.objects.filter(center_id=center_id, started_date__date=today, status=2).first()
        if completed:
            data.append({"name": "Class Ended", "type": 4, "id": completed.id, "startedDate": completed.started_date, "endDate": completed.end_date})
        return Response({"data": data, "status": True})


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


class StudentattendanceSavestudentattendancePostView(DotNetAPIView):
    """Implement the DAL's per-student, per-class attendance rules."""
    serializer_class = api_serializers.StudentAttendanceSaveRequestSerializer

    automatic = False
    manual = False

    def post(self, request, *args, **kwargs):
        data = self.validated_request_data
        student_id = data["StudentIds"][0]  # the .NET DAL processes the first id
        student = Student.objects.filter(pk=student_id, status=True).first()
        if not student:
            return self.attendance_result(0)
        if student.center_id != data["CenterId"]:
            return self.attendance_result(-2)
        scan_date = now() if (self.automatic or self.manual) else data["ScanDate"]
        if StudentAttendance.objects.filter(student_id=student_id, class_obj_id=data["ClassId"], scan_date__date=scan_date.date()).exists():
            return self.attendance_result(-1)
        if self.manual and (student.manual_attendance or 0) >= 360:
            return self.attendance_result(0)
        with transaction.atomic():
            StudentAttendance.objects.create(class_obj_id=data["ClassId"], student=student, center=student.center, user_id=data["UserId"], scan_date=scan_date, type=self.manual)
            Student.objects.filter(pk=student.pk).update(active_class_status=True)
            if self.manual:
                Student.objects.filter(pk=student.pk).update(manual_attendance=(student.manual_attendance or 0) + 1)
            ClassModel.objects.filter(pk=data["ClassId"]).update(avilable_students=Coalesce(F("avilable_students"), 0) + 1)
        return self.attendance_result(1)

    def attendance_result(self, result):
        if result == -1:
            message = "Student attendance already exists"
            response_status = status.HTTP_400_BAD_REQUEST if (self.automatic or self.manual) else status.HTTP_200_OK
        elif result == 0:
            message = "Manual attendance already exists with 6 times" if self.manual else "Student already inactive"
            response_status = status.HTTP_404_NOT_FOUND if self.manual else (status.HTTP_406_NOT_ACCEPTABLE if self.automatic else status.HTTP_200_OK)
        elif result == -2:
            message, response_status = "student not exists in center", (status.HTTP_404_NOT_FOUND if self.automatic else status.HTTP_200_OK)
        else:
            message, response_status = "Student attendance applied", status.HTTP_200_OK
        return ok(message=message, code=response_status)


class StudentattendanceSaveautomaticstudentattendancePostView(StudentattendanceSavestudentattendancePostView):
    """Compatibility view for automatic attendance save requests."""
    serializer_class = api_serializers.StudentAttendanceSaveRequestSerializer
    automatic = True


class StudentattendanceSavemanualstudentattendancePostView(StudentattendanceSavestudentattendancePostView):
    """Compatibility view for manual attendance save requests."""
    serializer_class = api_serializers.StudentAttendanceSaveRequestSerializer
    manual = True


class StudentattendanceGetallstudentwihavgattendanceGetView(DotNetAPIView):
    """Lists center students with their average attendance value."""
    serializer_class = api_serializers.StudentAttendanceCenterQuerySerializer

    def get(self, request, *args, **kwargs):
        center_id = request_value(request, "centerId", "CenterId")
        classes_count = ClassModel.objects.filter(center_id=center_id, status__in=[1, 2]).count()
        students = Student.objects.filter(center_id=center_id)
        data = []
        for student in students:
            attendance_count = StudentAttendance.objects.filter(student=student).count()
            data.append({"id": student.id, "enrollmentId": student.enrollment_id, "fullName": student.full_name,
                         "date": student.joining_date, "attendanceStatus": "1" if student.status else "0",
                         "averageAttendance": round(attendance_count * 100 / classes_count, 2) if classes_count else 0})
        return ok(data, "Students exists")


class StudentattendanceGetallabsentattendanceGetView(ModelListView):
    """Lists active students without attendance for the selected center."""
    serializer_class = api_serializers.StudentAttendanceCenterQuerySerializer
    model = Student
    message = "List of all active students exists"

    def get_queryset(self, request):
        center_id = request_value(request, "centerId", "CenterId")
        present_ids = StudentAttendance.objects.filter(center_id=center_id, scan_date__date=now().date()).values_list("student_id", flat=True)
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
            data.append({"id": student.id, "enrollmentId": student.enrollment_id, "fullName": student.full_name,
                         "attendanceStatus": "Present" if attendance.exists() else "Absent"})
        return ok(data, "Student status exists")


class StudentattendanceGetallstudentattendancbymonthGetView(DotNetAPIView):
    """Lists attendance records filtered by center, student, month, and year."""
    serializer_class = api_serializers.StudentAttendanceByMonthQuerySerializer
    def get(self, request, *args, **kwargs):
        import calendar
        center_id = request_value(request, "centerId", "CenterId")
        student_id = to_int(request_value(request, "studentId", "StudentId"))
        month, year = to_int(request_value(request, "month", "Month")), to_int(request_value(request, "year", "Year"))
        student = Student.objects.filter(pk=student_id, center_id=center_id, status=True).first()
        if not student or not month or not year:
            return ok([], "Student exists")
        data = []
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            date = datetime(year, month, day).date()
            present = StudentAttendance.objects.filter(student=student, scan_date__date=date).exists()
            data.append({"id": student.id, "fullName": student.full_name, "date": date, "attendanceStatus": "Present" if present else "Absent"})
        return ok(data, "Student exists")




class UserGetAllTeachersView(APIView):
    """Lists teachers, optionally filtered by creator user id."""
    
    def get(self, request):
        try:
            logger.info("UserController : GetRegisteredTeachers : Started")
            
            serializer = api_serializers.UserGetAllTeachersQuerySerializer(data=request.query_params)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            userId = serializer.validated_data.get('userId', 0)
            
            all_teachers = get_all_teachers(userId)
            
            if all_teachers is not None:
                response_serializer = api_serializers.TeacherDtoSerializer(all_teachers, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "List of assigned teachers",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "Asigned teachers not found",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserController : GetRegisteredTeachers : {str(e)}")
            return Response(
                {
                    "status": False,
                    "data": None,
                    "message": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )


class UserGetAllRegionalAdminsView(APIView):
    """Lists all regional admins."""
    
    def get(self, request):
        try:
            logger.info("UserController : GetAllRegionalAdmins : Started")
            
            all_regional_admins = get_all_regional_admins()
            
            if all_regional_admins is not None:
                response_serializer = api_serializers.RegionalAdminDtoSerializer(all_regional_admins, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "List of regional admins",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "List of regional admins not found",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserController : GetAllRegionalAdmins : {str(e)}")
            return Response(
                {
                    "status": False,
                    "data": None,
                    "message": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class UserLoginView(APIView):
    """Authenticates a user using mobile number and password"""
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        logger.info("UserController : LoginUser : Started")
        try:
            validate_app_and_device_with_token(request)
            mobile_number = request.data.get('mobileNumber')
            password = request.data.get('password')
            
            user = login_user(mobile_number, password)
            
            if user is not None:
                return Response(
                    {
                        "status": True,
                        "data": user,
                        "message": "Login successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "invalid credential",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as ex:
            logger.error(f"UserController : LoginUser exception: {str(ex)}")
            return Response(
                {
                    "status": False,
                    "error": str(ex),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )


class UserSaveSuperAdminView(APIView):
    """Saves a super admin user"""
    
    def post(self, request):
        try:
            logger.info("UserController : SaveSuperAdmin : Started")
            
            serializer = api_serializers.SuperAdminDtoSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_data = serializer.validated_data
            
            # Hash password
            if user_data.get('password'):
                user_data['password'] = hash_password(user_data['password'])
            
            saved_user = save_user(user_data)
            
            if saved_user:
                return Response(
                    {
                        "status": True,
                        "data": saved_user,
                        "message": "SuperAdmin save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "SuperAdmin doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserController : SaveSuperAdmin : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class UserUpdateDeviceIdView(APIView):
    """Updates user device ID"""
    
    def post(self, request):
        try:
            logger.info("UserController : UpdateDeviceId : Started")
            
            serializer = api_serializers.UserDeviceDtoSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_id = serializer.validated_data.get('userId')
            device_id = serializer.validated_data.get('deviceId')
            
            updated_user = update_user_device_id(user_id, device_id)
            
            if updated_user:
                return Response(
                    {
                        "status": True,
                        "data": updated_user,
                        "message": "SuperAdmin save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "SuperAdmin doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserController : UpdateDeviceId : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class UserSaveUserView(APIView):
    """Saves a user"""
    
    def post(self, request):
        try:
            logger.info("UserController : SaveUser : Started")
            
            # Check if Type=2 and ListOfPanchayatIds is missing
            if request.data.get('Type') == 2 and not request.data.get('ListOfPanchayatIds'):
                return Response(
                    {
                        "status": False,
                        "error": "ListOfPanchayatIds Parameter is missing",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = api_serializers.UserDtoSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_data = serializer.validated_data
            
            # Hash password if present
            if user_data.get('password'):
                user_data['password'] = hash_password(user_data['password'])
            
            saved_user = save_user(user_data)
            
            if saved_user:
                return Response(
                    {
                        "status": True,
                        "data": saved_user,
                        "message": "Data save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "data doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserController : SaveUser : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class UserUpdateSuperAdminUserView(UserSaveUserView):
    """Updates a super admin user"""
    pass

class UserGetUserByIdView(APIView):
    """Get user by ID"""
    
    def get(self, request):
        try:
            logger.info("UserController : GetUser : Started")
            
            user_id = request.query_params.get('userId')
            if not user_id:
                return Response(
                    {
                        "status": False,
                        "data": {},
                        "message": "user not exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            
            user = get_user_by_id(int(user_id))
            
            if user:
                return Response(
                    {
                        "status": True,
                        "data": user,
                        "message": "user exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": {},
                        "message": "user not exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserController : GetUser : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class UserGetUserDetailByPhoneNumberView(APIView):
    """Get user details by phone number"""
    
    def get(self, request):
        try:
            logger.info("UserController : GetUser : Started")
            
            phone_number = request.query_params.get('phoneNumer')
            if not phone_number:
                return Response(
                    {
                        "status": False,
                        "data": {},
                        "message": "user not exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            
            user = get_user_detail_by_phone(phone_number)
            
            if user:
                return Response(
                    {
                        "status": True,
                        "data": user,
                        "message": "user exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": {},
                        "message": "user not exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserController : GetUser : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class UserUpdatePasswordView(APIView):
    """Update user password"""
    
    def get(self, request):
        try:
            logger.info("UserController : GetUser : Started")
            
            serializer = api_serializers.UserUpdatePasswordQuerySerializer(data=request.query_params)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "data": {},
                        "message": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_id = serializer.validated_data.get('userId')
            new_password = serializer.validated_data.get('newPassword')
            
            user = update_user_password(user_id, new_password)
            
            if user:
                return Response(
                    {
                        "status": True,
                        "data": user,
                        "message": "password updated",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": {},
                        "message": "password not updated",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserController : UpdatePassword : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class UserGetAllUnAssignedTeacherView(ModelListView):
    """Lists teachers without an assigned center."""
    model = Teacher
    message = "List of teachers"

    def get_queryset(self, request):
        return Teacher.objects.filter(center__isnull=True).order_by("id")

class UserSearchDataView(APIView):
    """Search data by type and query string"""
    
    def get(self, request):
        try:
            logger.info("UserController : SearchData : Started")
            
            serializer = api_serializers.UserSearchDataQuerySerializer(data=request.query_params)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "message": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            search_type = serializer.validated_data.get('type', '')
            query_string = serializer.validated_data.get('queryString', '')
            
            results = search_data(search_type, query_string)
            
            if results is not None:
                return Response(
                    {
                        "status": True,
                        "data": results,
                        "message": "List of search data",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "message": "List of search data not found",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserController : SearchData : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )


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
