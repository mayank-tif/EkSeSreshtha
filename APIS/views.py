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


#---------------------------------------------------------
# Announcement Views
#---------------------------------------------------------

class AnnouncementSaveannouncementPostView(APIView):
    """Saves or updates announcement records from form or JSON data."""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveHolidays : Started")
            
            # Handle file upload
            image_files = request.FILES.getlist('ImageFile')
            image_paths = []
            
            if image_files:
                # Upload images
                for image_file in image_files:
                    if image_file:
                        import os
                        from django.core.files.storage import default_storage
                        from django.core.files.base import ContentFile
                        
                        file_extension = os.path.splitext(image_file.name)[1]
                        file_name = f"announcement_{uuid.uuid4()}{file_extension}"
                        file_path = f"AnnouncementImages/{file_name}"
                        
                        saved_path = default_storage.save(file_path, ContentFile(image_file.read()))
                        image_paths.append(default_storage.url(saved_path))
            
            # Prepare data for serializer
            data = request.data.copy()
            if image_paths:
                data['Image'] = ','.join(image_paths)
            
            serializer = api_serializers.AnnouncementSaveAnnouncementRequestSerializer(data=data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "details": serializer.errors,
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            announcement_data = serializer.validated_data
            saved_announcement = save_announcement(announcement_data)
            
            if saved_announcement:
                response_serializer = api_serializers.AnnouncementDtoSerializer(saved_announcement)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Announcement save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Announcement doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveAnnouncement : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class AnnouncementGetannouncementGetView(APIView):
    """Returns the announcement list ordered by the model defaults."""
    
    def get(self, request):
        try:
            logger.info("DistrictView : GetAnnouncement : Started")
            
            announcements = get_all_announcements()
            
            if announcements is not None and len(announcements) > 0:
                response_serializer = api_serializers.AnnouncementDtoSerializer(announcements, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "List of announcements",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "List of announcements not found",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"DistrictView : GetAnnouncement : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

#---------------------------------------------------------
# Center Views
#---------------------------------------------------------

class CenterSavecenterPostView(APIView):
    """Saves or updates a center."""
    
    def post(self, request):
        try:
            logger.info("CenterView : SaveCenter : Started")
            
            data = request.data.copy()
            
            # If updating, remove CenterGuidId to prevent duplicate key error
            if data.get('Id') and int(data.get('Id')) > 0:
                data.pop('CenterGuidId', None)
            
            # Parse StartedDate
            if 'StartedDate' in data and data['StartedDate']:
                try:
                    date_str = data['StartedDate'].replace('Z', '+00:00')
                    data['StartedDate'] = datetime.fromisoformat(date_str)
                except (ValueError, AttributeError):
                    pass
            
            logger.info(f"CenterSavecenterPostView data: {data}")
            
            serializer = api_serializers.CenterSaveCenterRequestSerializer(data=data)
            if not serializer.is_valid():
                logger.error(f"CenterSavecenterPostView validation errors: {serializer.errors}")
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "details": serializer.errors,
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            center_data = serializer.validated_data
            saved_center = save_center(center_data, request)
            
            if saved_center:
                response_serializer = api_serializers.CenterDetailDtoSerializer(saved_center)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Center save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Center doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"CenterView : SaveCenter : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )


class CommonCheckusermobilenumberPostView(CenterSavecenterPostView):
    """Compatibility alias for the .NET Common/CheckUserMobileNumber route."""
    serializer_class = api_serializers.CenterSaveCenterRequestSerializer


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
    
class CenterGetcenteryidGetView(APIView):
    """Returns a single center by the centeId query parameter."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetUser : Started")
            
            serializer = api_serializers.CenterGetCenteryIdQuerySerializer(data=request.query_params)
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
            
            center_id = serializer.validated_data.get('centeId')
            center = get_center_by_id(center_id)
            
            if center:
                response_serializer = api_serializers.CenterDetailDtoSerializer(center)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "center exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "center not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetCenterById : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class CenterGetcenterbyteacheridGetView(APIView):
    """Returns the center assigned to a teacher."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetStudentAttendanceOfCenter : Started")
            
            user_id = request.query_params.get('userId')
            if not user_id:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "center detail not found",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            center = get_center_by_user_id(int(user_id))
            
            if center:
                response_serializer = api_serializers.CenterDetailDtoSerializer(center)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "center detail",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "center detail not found",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetCenterByTeacherId : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class CenterGetallcenterattendanceGetView(APIView):
    """Returns center records with attendance and student counts for a date."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetAllCenterAttendance : Started")
            
            user_id = request.query_params.get('userId')
            date = request.query_params.get('date')
            offset = request.query_params.get('offset', 0)
            limit = request.query_params.get('limit', 0)
            if not offset:
                offset = 0
            if not limit:
                limit = 0
            
            if not user_id or not date:
                return Response(
                    {
                        "status": False,
                        "message": "userId and date are required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            centers = get_all_center_attendance(
                int(user_id), 
                date, 
                int(offset), 
                int(limit)
            )
            
            if centers is not None and len(centers) > 0:
                return Response(
                    {
                        "status": True,
                        "data": centers,
                        "message": "Centers available",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "message": "Centers not available",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetAllCenterAttendance : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class CenterUpdatecenteractiveordeactiveGetView(APIView):
    """Toggles or sets center status and records the reason in CenterLog."""
    
    def get(self, request):
        try:
            logger.info("UserView : UpdateCenterActiveOrDeactive : Started")
            
            center_id = request.query_params.get('centerId')
            status_value = request.query_params.get('status')
            user_id = request.query_params.get('userId')
            reason = request.query_params.get('reason')
            
            if not center_id:
                return Response(
                    {
                        "status": True,
                        "message": "Center status not updated",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            
            # Convert status to boolean
            if status_value is not None:
                status = to_bool(status_value)
            else:
                # Get current status and toggle
                with connection.cursor() as cursor:
                    cursor.execute("SELECT Status FROM Center WHERE Id = %s", [center_id])
                    row = cursor.fetchone()
                    if row:
                        current_status = row[0]
                        status = not current_status
                    else:
                        return Response(
                            {
                                "status": True,
                                "message": "Center status not updated",
                                "code": status.HTTP_200_OK
                            },
                            status=status.HTTP_200_OK
                        )
            
            center_log_data = {
                'centerId': int(center_id),
                'status': status,
                'userId': int(user_id) if user_id else None,
                'reason': reason
            }
            
            result = update_center_active_or_deactive(center_log_data)
            
            if result:
                return Response(
                    {
                        "status": True,
                        "message": "Center status updated",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": True,
                        "message": "Center status not updated",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserView : UpdateCenterActiveOrDeactive : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class CenterGettotalattendancecountofcenterGetView(APIView):
    """Returns aggregate attendance, student, and center counts."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetTotalAttendanceCountOfCenter : Started")
            
            user_id = request.query_params.get('userId')
            date = request.query_params.get('date')
            
            if not user_id or not date:
                return Response(
                    {
                        "status": False,
                        "message": "userId and date are required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            result = get_total_attendance_count_of_center(int(user_id), date)
            
            if result:
                return Response(
                    {
                        "data": result,
                        "status": True,
                        "message": "Center exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "message": "Center not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetTotalAttendanceCountOfCenter : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )


#---------------------------------------------------------
# Class Views
#---------------------------------------------------------

class ClassSaveclassPostView(APIView):
    """Saves a new class"""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveClass : Started")
            
            serializer = api_serializers.ClassSaveClassRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data = serializer.validated_data
            class_data = {
                'classEnrolmentId': data.get('ClassEnrolmentId') or str(uuid.uuid4()),
                'name': data.get('Name'),
                'centerId': data.get('CenterId'),
                'userId': data.get('UserId'),
                'totalStudents': data.get('TotalStudents'),
                'avilableStudents': data.get('AvilableStudents')
            }
            
            saved_class = save_class(class_data)
            
            if saved_class:
                return Response(
                    {
                        "status": True,
                        "data": saved_class,
                        "message": "Class save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Class already exists",
                        "code": status.HTTP_409_CONFLICT
                    },
                    status=status.HTTP_409_CONFLICT
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveClass : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class ClassCancelclassPostView(APIView):
    """Cancels a class"""
    
    def post(self, request):
        try:
            logger.info("UserView : CancelClass : Started")
            
            serializer = api_serializers.CancelClassDtoSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            class_data = serializer.validated_data
            result = cancel_class(class_data)
            
            if result:
                return Response(
                    {
                        "status": True,
                        "message": "Class canceled successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Class not canceled",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : CancelClass : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class ClassUpdateendclasstimePostView(APIView):
    """Updates end class time"""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveClass : Started")
            
            serializer = api_serializers.EndClassDtoSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            class_id = serializer.validated_data.get('id')
            result = update_end_class_time(class_id)
            
            if result:
                return Response(
                    {
                        "status": True,
                        "message": "Time updated",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Time not updated",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveClass : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class ClassUpdateclasssubstatusPostView(APIView):
    """Updates class sub status"""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveClass : Started")
            
            serializer = api_serializers.UpdateClassSubStatusDtoSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            class_id = serializer.validated_data.get('id')
            result = update_class_sub_status(class_id)
            
            if result:
                return Response(
                    {
                        "status": True,
                        "message": "Status updated",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Status not updated",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveClass : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class ClassCancelclassbyteacherPostView(APIView):
    """Cancel class by teacher"""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveClass : Started")
            
            serializer = api_serializers.ClassCancelTeacherDtoSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data = serializer.validated_data
            result = cancel_class_by_teacher(data)
            
            if result:
                return Response(
                    {
                        "status": True,
                        "message": "Class cancelled",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Class not cancelled",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveClass : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class ClassDeleteclassbyteacheridPostView(APIView):
    """Delete class by teacher ID"""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveClass : Started")
            
            serializer = api_serializers.ClassDeleteClassByTeacherIdQuerySerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            class_id = serializer.validated_data.get('classId')
            result = delete_class_by_teacher_id(class_id)
            
            if result:
                return Response(
                    {
                        "status": True,
                        "message": "class deleted",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "class not deleted",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveClass : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class ClassGetclasscurrentstatusGetView(APIView):
    """Returns current class status"""
    
    def get(self, request):
        try:
            logger.info("UserView : SaveClass : Started")
            
            serializer = api_serializers.ClassGetClassCurrentStatusQuerySerializer(data=request.query_params)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            center_id = serializer.validated_data.get('centerId')
            teacher_id = serializer.validated_data.get('teacherId')
            
            result = get_class_current_status(center_id, teacher_id)
            
            return Response(result, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"UserView : SaveClass : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class ClassGetliveclassdetailGetView(APIView):
    """Returns live class detail"""
    
    def get(self, request):
        try:
            logger.info("UserView : SaveClass : Started")
            
            serializer = api_serializers.ClassGetLiveClassDetailQuerySerializer(data=request.query_params)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            class_id = serializer.validated_data.get('classId')
            class_data = get_live_class_detail(class_id)
            
            if class_data:
                response_serializer = api_serializers.ClassLiveDetailDtoSerializer(class_data)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "class detail exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Class detail not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveClass : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

#---------------------------------------------------------
# District Views
#---------------------------------------------------------

class DistrictGetalldistrictGetView(APIView):
    """Lists districts with optional offset/limit pagination."""
    
    def get(self, request):
        try:
            logger.info("DistrictView : GetAllDistrict : Started")
            
            serializer = api_serializers.PaginationQuerySerializer(data=request.query_params)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "message": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            offset = serializer.validated_data.get('offset', 0)
            limit = serializer.validated_data.get('limit', 0)
            
            districts = get_all_districts(offset, limit)
            
            if districts is not None and len(districts) > 0:
                response_serializer = api_serializers.DistrictDtoSerializer(districts, many=True)
                return Response(
                    {
                        "status": True,
                        "message": "List of district",
                        "data": response_serializer.data,
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "message": "List of district not found",
                        "data": None,
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"DistrictView : GetAllDistrict : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class DistrictSavedistrictPostView(APIView):
    """Saves or updates a district and creates a guid when needed."""
    
    def post(self, request):
        try:
            logger.info("DistrictView : SaveDistrict : Started")
            
            serializer = api_serializers.DistrictSaveDistrictRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            district_data = serializer.validated_data
            saved_district = save_district(district_data)
            
            if saved_district:
                response_serializer = api_serializers.DistrictDtoSerializer(saved_district)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "District save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "District doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"DistrictView : SaveDistrict : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )


#---------------------------------------------------------
# VidhanSabha Views
#---------------------------------------------------------

class VidhansabhaGetallvidhansabhaGetView(APIView):
    """Lists Vidhan Sabha records with optional pagination."""
    
    def get(self, request):
        try:
            logger.info("VidhanSabhaView : GetAllVidhanSabha : Started")
            
            offset = request.query_params.get('offset', 0)
            limit = request.query_params.get('limit', 0)
            
            vidhan_sabhas = get_all_vidhan_sabhas(int(offset), int(limit))
            
            if vidhan_sabhas is not None and len(vidhan_sabhas) > 0:
                response_serializer = api_serializers.VidhanSabhaDtoSerializer(vidhan_sabhas, many=True)
                return Response(
                    {
                        "status": True,
                        "message": "List of vidhanSabha",
                        "data": response_serializer.data,
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "message": "List of vidhanSabha not found",
                        "data": None,
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"VidhanSabhaView : GetAllVidhanSabha : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class VidhansabhaSavevidhansabhaPostView(APIView):
    """Saves or updates a Vidhan Sabha record."""
    
    def post(self, request):
        try:
            logger.info("VidhanSabhaView : SaveVidhanSabha : Started")
            
            serializer = api_serializers.VidhanSabhaSaveVidhanSabhaRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            vidhan_sabha_data = serializer.validated_data
            saved_vidhan_sabha = save_vidhan_sabha(vidhan_sabha_data)
            
            if saved_vidhan_sabha:
                response_serializer = api_serializers.VidhanSabhaDtoSerializer(saved_vidhan_sabha)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "VidanSabha save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "VidanSabha doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"VidhanSabhaView : SaveVidhanSabha : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class VidhansabhaGetvidhansabhabydistrictidGetView(APIView):
    """Lists Vidhan Sabha records for a district."""
    
    def get(self, request):
        try:
            logger.info("VidhanSabhaView : GetVidhanSabhaByDistrictId : Started")
            
            district_id = request.query_params.get('districtId')
            if not district_id:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "districtId is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            vidhan_sabha = get_vidhan_sabha_by_district_id(int(district_id))
            
            if vidhan_sabha:
                response_serializer = api_serializers.VidhanSabhaDtoSerializer(vidhan_sabha)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "VidanSabha exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "VidanSabha not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"VidhanSabhaView : GetVidhanSabhaByDistrictId : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VidhansabhaCheckvidhansabhanamePostView(APIView):
    """Checks whether a Vidhan Sabha name already exists."""
    
    def post(self, request):
        try:
            logger.info("UserView : CheckVidhanSabhaName : Started")
            
            name = request.data.get('name')
            if not name:
                return Response(
                    {
                        "status": False,
                        "error": "name is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            exists = check_vidhan_sabha_name(name)
            
            if exists:
                return Response(
                    {
                        "status": False,
                        "message": "VidhanSabha name already exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "VidhanSabha name doesn't exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : CheckVidhanSabhaName : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

#---------------------------------------------------------
# Panchayat Views
#---------------------------------------------------------

class PanchayatGetallpanchayatGetView(APIView):
    """Lists panchayats with optional pagination."""
    
    def get(self, request):
        try:
            logger.info("PanchayatView : GetAllPanchayat : Started")
            
            offset = request.query_params.get('offset', 0)
            limit = request.query_params.get('limit', 0)
            
            panchayats = get_all_panchayats(int(offset), int(limit))
            
            if panchayats is not None and len(panchayats) > 0:
                response_serializer = api_serializers.PanchayatDtoSerializer(panchayats, many=True)
                return Response(
                    {
                        "status": True,
                        "message": "List of panchayat",
                        "data": response_serializer.data,
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "message": "List of panchayat not found",
                        "data": None,
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"PanchayatView : GetAllPanchayat : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class PanchayatSavepanchayatPostView(APIView):
    """Saves or updates a panchayat record."""
    
    def post(self, request):
        try:
            logger.info("PanchayatView : SavePanchayat : Started")
            
            serializer = api_serializers.PanchayatSavePanchayatRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            panchayat_data = serializer.validated_data
            saved_panchayat = save_panchayat(panchayat_data)
            
            if saved_panchayat:
                response_serializer = api_serializers.PanchayatDtoSerializer(saved_panchayat)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Panchayat save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Panchayat doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"PanchayatView : SavePanchayat : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class PanchayatGetpanchayatbydistrictandvidhansabhaidGetView(APIView):
    """Lists panchayats for a district and Vidhan Sabha."""
    
    def get(self, request):
        try:
            logger.info("VidhanSabhaView : GetPanchayatByDistrictAndVidhanSabhaId : Started")
            
            district_id = request.query_params.get('districtId')
            vidhan_sabha_id = request.query_params.get('vidhanSabhaId')
            
            if not district_id or not vidhan_sabha_id:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "districtId and vidhanSabhaId are required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            panchayat = get_panchayat_by_district_and_vidhan_sabha_id(
                int(district_id), int(vidhan_sabha_id)
            )
            
            if panchayat:
                response_serializer = api_serializers.PanchayatDtoSerializer(panchayat)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Panchayat exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "Panchayat not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"VidhanSabhaView : GetPanchayatByDistrictAndVidhanSabhaId : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class PanchayatCheckpanchayatnamePostView(APIView):
    """Checks whether a panchayat name already exists."""
    
    def post(self, request):
        try:
            logger.info("UserView : CheckPanchayatName : Started")
            
            name = request.data.get('name')
            if not name:
                return Response(
                    {
                        "status": False,
                        "error": "name is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            exists = check_panchayat_name(name)
            
            if exists:
                return Response(
                    {
                        "status": False,
                        "message": "Panchayat name already exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": True,
                        "error": "Panchayat name doesn't exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : CheckPanchayatName : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )


#---------------------------------------------------------
# Village Views
#---------------------------------------------------------

class VillageGetallvillageGetView(APIView):
    """Lists villages with optional pagination."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetAllVillage : Started")
            
            offset = request.query_params.get('offset', 0)
            limit = request.query_params.get('limit', 0)
            
            villages = get_all_villages(int(offset), int(limit))
            
            if villages is not None and len(villages) > 0:
                response_serializer = api_serializers.VillageDtoSerializer(villages, many=True)
                return Response(
                    {
                        "status": True,
                        "message": "List of villages",
                        "data": response_serializer.data,
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "message": "List of villages not found",
                        "data": None,
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"VillageView : GetAllVillage : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class VillageSavevillagePostView(APIView):
    """Saves or updates a village record."""
    
    def post(self, request):
        try:
            logger.info("VillageView : SaveVillage : Started")
            
            serializer = api_serializers.VillageSaveVillageRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            village_data = serializer.validated_data
            saved_village = save_village(village_data)
            
            if saved_village:
                response_serializer = api_serializers.VillageDtoSerializer(saved_village)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Village save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Village doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"VillageView : SaveVillage : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class VillageGetvillagebydistrictvidhansabhaandpanchidGetView(APIView):
    """Lists villages by district, Vidhan Sabha, and panchayat."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetVillageByDistrictVidhanSabhaAndPanchId : Started")
            
            district_id = request.query_params.get('districtId')
            vidhan_sabha_id = request.query_params.get('vidhanSabhaId')
            panchayat_id = request.query_params.get('panchayatId')
            
            if not district_id or not vidhan_sabha_id or not panchayat_id:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "districtId, vidhanSabhaId and panchayatId are required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            village = get_village_by_district_vidhan_sabha_and_panchayat(
                int(district_id), int(vidhan_sabha_id), int(panchayat_id)
            )
            
            if village:
                response_serializer = api_serializers.VillageDtoSerializer(village)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Village exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "Village not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"VillageView : GetVillageByDistrictVidhanSabhaAndPanchId : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class VillageCheckvillagenamePostView(APIView):
    """Checks whether a village name already exists."""
    
    def post(self, request):
        try:
            logger.info("UserView : CheckVillageName : Started")
            
            name = request.data.get('name')
            if not name:
                return Response(
                    {
                        "status": False,
                        "error": "name is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            exists = check_village_name(name)
            
            if exists:
                return Response(
                    {
                        "status": False,
                        "message": "Village name already exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": True,
                        "error": "Village name doesn't exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : CheckVillageName : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )


#---------------------------------------------------------
# School Views
#---------------------------------------------------------

class SchoolSaveschoolPostView(APIView):
    """Saves or updates a school record."""
    
    def post(self, request):
        try:
            logger.info("UserView : LoginSuperAdmin : Started")
            
            serializer = api_serializers.SchoolSaveSchoolRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            school_data = serializer.validated_data
            saved_school = save_school(school_data)
            
            if saved_school:
                response_serializer = api_serializers.SchoolDtoSerializer(saved_school)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "School save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "School doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveSchool : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class SchoolGetallschoolsGetView(APIView):
    """Returns all school records."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetUser : Started")
            
            schools = get_all_schools()
            
            if schools is not None and len(schools) > 0:
                response_serializer = api_serializers.SchoolDtoSerializer(schools, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "school exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "school not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetAllSchools : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )


#---------------------------------------------------------
# Holidays Views
#---------------------------------------------------------

class HolidaysSaveholidaysPostView(APIView):
    """Saves or updates holiday records."""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveHolidays : Started")
            
            # Get data from request
            data = request.data.copy()
            
            # Ensure ListCenterIds is a string and has valid values
            if 'ListCenterIds' in data:
                if isinstance(data['ListCenterIds'], list):
                    data['ListCenterIds'] = ','.join(str(x) for x in data['ListCenterIds'] if x)
                elif data['ListCenterIds'] is None:
                    data['ListCenterIds'] = ''
            
            # Parse dates from ISO format
            date_fields = ['StartDate', 'EndDate', 'CreatedOn']
            for field in date_fields:
                if field in data and data[field]:
                    try:
                        date_str = data[field].replace('Z', '+00:00')
                        data[field] = datetime.fromisoformat(date_str)
                    except (ValueError, AttributeError):
                        return Response(
                            {
                                "status": False,
                                "error": f"Invalid date format for {field}. Expected ISO format like 2026-07-15T09:21:32.948Z",
                                "code": status.HTTP_400_BAD_REQUEST
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            logger.info(f"HolidaysSaveholidaysPostView data: {data}")
            
            serializer = api_serializers.HolidaysSaveHolidaysRequestSerializer(data=data)
            if not serializer.is_valid():
                logger.error(f"HolidaysSaveholidaysPostView validation errors: {serializer.errors}")
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "details": serializer.errors,
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            holidays_data = serializer.validated_data
            result = save_holidays(holidays_data)
            
            if result:
                holiday_id = holidays_data.get('Id', 0)
                if holiday_id > 0:
                    message = "Holdays update successfully"
                else:
                    message = "Holdays save successfully"
                
                return Response(
                    {
                        "status": True,
                        "message": message,
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Holdays doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveHolidays : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )
            
class HolidaysGetallholidaysbyteacheridGetView(APIView):
    """Lists holidays for the center assigned to a teacher."""
    
    def get(self, request):
        try:
            logger.info("DistrictView : GetAllDistrict : Started")
            
            teacher_id = request.query_params.get('teacherId')
            if not teacher_id:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "teacherId is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            holidays = get_all_holidays_by_teacher_id(int(teacher_id))
            
            if holidays is not None and len(holidays) > 0:
                response_serializer = api_serializers.HolidaysDtoSerializer(holidays, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "List of Holidays",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "List of Holidays not found",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"DistrictView : GetAllHolidaysByTeacherId : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class HolidaysGetallholidaysbycenteridGetView(APIView):
    """Lists holidays for a center."""
    
    def get(self, request):
        try:
            logger.info("DistrictView : GetAllDistrict : Started")
            
            center_id = request.query_params.get('centerId')
            if not center_id:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "centerId is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            holidays = get_all_holidays_by_center_id(int(center_id))
            
            if holidays is not None and len(holidays) > 0:
                response_serializer = api_serializers.HolidaysDtoSerializer(holidays, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "List of Holidays exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "Holidays not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"DistrictView : GetAllHolidaysByCenterId : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class HolidaysGetallholidaysbyyearGetView(APIView):
    """Lists holidays whose start date falls in a year."""
    
    def get(self, request):
        try:
            logger.info("DistrictView : GetAllHolidaysByYear : Started")
            
            year = request.query_params.get('year')
            if not year:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "year is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            holidays = get_all_holidays_by_year(int(year))
            
            if holidays is not None and len(holidays) > 0:
                response_serializer = api_serializers.HolidaysDtoSerializer(holidays, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "List of Holidays",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "List of Holidays not found",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"DistrictView : GetAllHolidaysByYear : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class HolidaysGetallholidaysGetView(APIView):
    """Lists holidays, optionally filtered by status."""
    
    def get(self, request):
        try:
            logger.info("DistrictView : GetAllHolidaysByYear : Started")
            
            status_param = request.query_params.get('status', 1)
            user_id = request.query_params.get('userId', 0)
            
            holidays = get_all_holidays(int(status_param), int(user_id))
            
            if holidays is not None and len(holidays) > 0:
                response_serializer = api_serializers.HolidaysDtoSerializer(holidays, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "List of Holidays",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": {},
                        "message": "List of Holidays not found",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"DistrictView : GetAllHolidays : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class HolidaysDeleteholidaybyidPostView(APIView):
    """Deletes a holiday by id."""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveClass : Started")
            
            holiday_id = request.data.get('id')
            if not holiday_id:
                return Response(
                    {
                        "status": False,
                        "error": "id is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            result = delete_holiday_by_id(int(holiday_id))
            
            if result:
                return Response(
                    {
                        "status": True,
                        "message": "holiday deleted",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "holiday not deleted",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserView : DeleteHolidayById : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )


#---------------------------------------------------------
# Student Views
#---------------------------------------------------------

class StudentSavestudentPostView(APIView):
    """Saves or updates student details and creates enrollment id when missing."""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveStudent : Started")
            
            # Get data from request
            data = request.data.copy()
            
            # Parse dates from ISO format
            date_fields = ['JoiningDate', 'CreatedOn']
            for field in date_fields:
                if field in data and data[field]:
                    try:
                        date_str = data[field].replace('Z', '+00:00')
                        data[field] = datetime.fromisoformat(date_str)
                    except (ValueError, AttributeError):
                        return Response(
                            {
                                "status": False,
                                "error": f"Invalid date format for {field}",
                                "code": status.HTTP_400_BAD_REQUEST
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            # Convert Bpl to boolean
            if 'Bpl' in data:
                if isinstance(data['Bpl'], str):
                    data['Bpl'] = data['Bpl'].lower() in ['true', '1', 'yes']
            
            logger.info(f"StudentSavestudentPostView data: {data}")
            
            serializer = api_serializers.StudentSaveStudentRequestSerializer(data=data)
            if not serializer.is_valid():
                logger.error(f"StudentSavestudentPostView validation errors: {serializer.errors}")
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "details": serializer.errors,
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            student_data = serializer.validated_data
            saved_student = save_student(student_data)
            
            if saved_student:
                response_serializer = api_serializers.StudentDtoSerializer(saved_student)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Student save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Student doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveStudent : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class StudentGetstudentbyidGetView(APIView):
    """Returns a student by student id."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetUser : Started")
            
            student_id = request.query_params.get('studentId')
            if not student_id:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "studentId is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            student = get_student_by_id(int(student_id))
            
            if student:
                response_serializer = api_serializers.StudentDetailDtoSerializer(student)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "student exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "student not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetStudentById : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class StudentUpdatestudentactiveorinactivePostView(APIView):
    """Updates a student active/inactive status."""
    
    def post(self, request):
        try:
            logger.info("UserView : UpdateStudentActiveOrInactive : Started")
            
            serializer = api_serializers.StudentUpdateStudentActiveOrInactiveRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            student_id = serializer.validated_data.get('Id')
            status_val = serializer.validated_data.get('Status')
            
            student = update_student_active_or_inactive(student_id, status_val)
            
            if student:
                response_serializer = api_serializers.StudentDtoSerializer(student)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Status updated",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "Status not updated",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : UpdateStudentActiveOrInactive : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class StudentGettotalstudentpresentGetView(APIView):
    """Returns total present student attendance count for an optional date."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetTotalStudentPresent : Started")
            
            scan_date = request.query_params.get('scanDate')
            user_id = request.query_params.get('userId')
            
            # if not scan_date or not user_id:
            #     return Response(
            #         {
            #             "status": False,
            #             "data": None,
            #             "message": "scanDate and userId are required",
            #             "code": status.HTTP_400_BAD_REQUEST
            #         },
            #         status=status.HTTP_400_BAD_REQUEST
            #     )
            
            scan_date = parse_any_datetime(scan_date)
            result = get_total_student_present(scan_date, int(user_id))
            
            if result:
                response_serializer = api_serializers.StudentPresentClassDtoSerializer(result)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Total count",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": {},
                        "message": "Not found",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserView : GetTotalStudentPresent : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class StudentGetallstudentsGetView(APIView):
    """Lists students filtered by optional location identifiers."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetTotalStudentPresent : Started")
            
            user_id = request.query_params.get('userId')
            if not user_id:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "userId is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            district_id = request.query_params.get('districtId', 0)
            vidhan_sabha_id = request.query_params.get('vidhanSabhaId', 0)
            panchayat_id = request.query_params.get('panchayatId', 0)
            village_id = request.query_params.get('villageId', 0)
            
            students = get_all_students(
                int(user_id),
                int(district_id),
                int(vidhan_sabha_id),
                int(panchayat_id),
                int(village_id)
            )
            
            if students is not None and len(students) > 0:
                response_serializer = api_serializers.StudentDtoSerializer(students, many=True)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Total students",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": {},
                        "message": "Not found",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserView : GetAllStudents : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

#---------------------------------------------------------
# StudentAttendance Views
#---------------------------------------------------------

class StudentattendanceSavestudentattendancePostView(APIView):
    """Saves student attendance"""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveStudentAttendance : Started")
            
            serializer = api_serializers.StudentAttendanceSaveRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            attendance_data = serializer.validated_data
            result = save_student_attendance(attendance_data, is_automatic=False, is_manual=False)
            
            if result == -1:
                return Response(
                    {
                        "status": True,
                        "message": "Student attendance already exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            elif result == 0:
                return Response(
                    {
                        "status": True,
                        "message": "Student already inactive",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            elif result == -2:
                return Response(
                    {
                        "status": True,
                        "message": "student not exists in center",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": True,
                        "message": "Student attendance applied",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveStudentAttendance : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class StudentattendanceSaveautomaticstudentattendancePostView(APIView):
    """Saves automatic student attendance"""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveStudentAttendance : Started")
            
            serializer = api_serializers.StudentAttendanceSaveRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            attendance_data = serializer.validated_data
            result = save_student_attendance(attendance_data, is_automatic=True, is_manual=False)
            
            if result == -1:
                return Response(
                    {
                        "status": True,
                        "message": "Student attendance already exists",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif result == 0:
                return Response(
                    {
                        "status": True,
                        "message": "Student already inactive",
                        "code": status.HTTP_406_NOT_ACCEPTABLE
                    },
                    status=status.HTTP_406_NOT_ACCEPTABLE
                )
            elif result == -2:
                return Response(
                    {
                        "status": True,
                        "message": "student not exists in center",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                return Response(
                    {
                        "status": True,
                        "message": "Student attendance applied",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveAutomaticStudentAttendance : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class StudentattendanceSavemanualstudentattendancePostView(APIView):
    """Saves manual student attendance"""
    
    def post(self, request):
        try:
            logger.info("UserView : SaveStudentAttendance : Started")
            
            serializer = api_serializers.StudentAttendanceSaveRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            attendance_data = serializer.validated_data
            result = save_student_attendance(attendance_data, is_automatic=False, is_manual=True)
            
            if result == -1:
                return Response(
                    {
                        "status": True,
                        "message": "Student attendance already exists",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif result == 0:
                return Response(
                    {
                        "status": True,
                        "message": "Manual attendance already exists with 6 times",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                return Response(
                    {
                        "status": True,
                        "message": "Student attendance applied",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveManualStudentAttendance : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class StudentattendanceGetallstudentwihavgattendanceGetView(APIView):
    """Lists center students with their average attendance value."""
    
    def get(self, request):
        try:
            logger.info("UserView : SaveStudentAttendance : Started")
            
            center_id = request.query_params.get('centerId')
            if not center_id:
                return Response(
                    {
                        "status": False,
                        "error": "centerId is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            students = get_all_student_with_avg_attendance(int(center_id))
            
            if students is not None and len(students) > 0:
                return Response(
                    {
                        "status": True,
                        "data": students,
                        "message": "Students exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Students not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetAllStudentWihAvgAttendance : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class StudentattendanceGetallabsentattendanceGetView(APIView):
    """Lists active students without attendance for the selected center."""
    
    def get(self, request):
        try:
            logger.info("UserView : SaveStudentAttendance : Started")
            
            center_id = request.query_params.get('centerId')
            if not center_id:
                return Response(
                    {
                        "status": False,
                        "error": "centerId is required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            students = get_all_absent_attendance(int(center_id))
            
            if students is not None and len(students) > 0:
                return Response(
                    {
                        "status": True,
                        "data": students,
                        "message": "List of all active students exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Active students not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetAllAbsentAttendance : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class StudentattendanceGetallstudentattendancstatusGetView(APIView):
    """Lists students with present/absent status for a center and date."""
    
    def get(self, request):
        try:
            logger.info("UserView : SaveStudentAttendance : Started")
            
            center_id = request.query_params.get('centerId')
            scan_date = request.query_params.get('scanDate')
            
            # if not center_id or not scan_date:
            #     return Response(
            #         {
            #             "status": False,
            #             "error": "centerId and scanDate are required",
            #             "code": status.HTTP_400_BAD_REQUEST
            #         },
            #         status=status.HTTP_400_BAD_REQUEST
            #     )
            
            students = get_all_student_attendance_status(int(center_id), scan_date)
            
            if students is not None and len(students) > 0:
                return Response(
                    {
                        "status": True,
                        "data": students,
                        "message": "Student status exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Student status not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetAllStudentAttendancStatus : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class StudentattendanceGetallstudentattendancbymonthGetView(APIView):
    """Lists attendance records filtered by center, student, month, and year."""
    
    def get(self, request):
        try:
            logger.info("UserView : SaveStudentAttendance : Started")
            
            center_id = request.query_params.get('centerId')
            student_id = request.query_params.get('studentId')
            month = request.query_params.get('month')
            year = request.query_params.get('year')
            
            if not center_id or not student_id or not month or not year:
                return Response(
                    {
                        "status": False,
                        "error": "centerId, studentId, month and year are required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            students = get_all_student_attendance_by_month(int(center_id), int(student_id), int(month), int(year))
            
            if students is not None and len(students) > 0:
                return Response(
                    {
                        "status": True,
                        "data": students,
                        "message": "Student exists",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Student not exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetAllStudentAttendancByMonth : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )
    
#---------------------------------------------------------
# User Views
#---------------------------------------------------------
class UserGetAllTeachersView(APIView):
    """Lists teachers, optionally filtered by creator user id."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetRegisteredTeachers : Started")
            
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
                response_serializer = api_serializers.TeacherDetailSerializer(all_teachers, many=True)
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
            logger.error(f"UserView : GetRegisteredTeachers : {str(e)}")
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
            logger.info("UserView : GetAllRegionalAdmins : Started")
            
            all_regional_admins = get_all_regional_admins()
            
            if all_regional_admins is not None:
                response_serializer = api_serializers.RegionalAdminDetailSerializer(all_regional_admins, many=True)
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
            logger.error(f"UserView : GetAllRegionalAdmins : {str(e)}")
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
        logger.info("UserView : LoginUser : Started")
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
            logger.error(f"UserView : LoginUser exception: {str(ex)}")
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
            logger.info("UserView : SaveSuperAdmin : Started")
            
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
            logger.error(f"UserView : SaveSuperAdmin : {str(e)}")
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
            logger.info("UserView : UpdateDeviceId : Started")
            
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
            device_id = serializer.validated_data.get('DeviceId')
            
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
            logger.error(f"UserView : UpdateDeviceId : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class UserSaveUserView(APIView):
    def post(self, request):
        try:
            logger.info("UserView : SaveUser : Started")
            
            # Get the raw data for processing
            data = request.data.copy()
            print("data", data)
            
            # Handle ListOfPanchayatIds from form data
            if 'ListOfPanchayatIds' in data:
                if isinstance(data['ListOfPanchayatIds'], list):
                    data['ListOfPanchayatIds'] = ','.join(str(x) for x in data['ListOfPanchayatIds'])
            
            # Log the data for debugging
            logger.info(f"UserSaveUserView data: {data}")
            
            serializer = api_serializers.UserSaveUserRequestSerializer(data=data)
            
            if not serializer.is_valid():
                logger.error(f"UserSaveUserView validation errors: {serializer.errors}")
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "details": serializer.errors,
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_data = serializer.validated_data
            
            # Hash password if present
            if user_data.get('Password'):
                user_data['Password'] = hash_password(user_data['Password'])
            
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
            logger.error(f"UserView : SaveUser : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class UserUpdateSuperAdminUserView(APIView):
    """Updates a super admin user"""
    
    def post(self, request):
        try:
            logger.info("UserView : UpdateSuperAdminUser : Started")
            
            # Get data from request
            data = request.data.copy()
            
            # Hash password if present
            if data.get('Password'):
                data['Password'] = hash_password(data['Password'])
            
            # Parse dates from ISO format
            date_fields = ['CreatedOn', 'EnrollmentDate']
            for field in date_fields:
                if field in data and data[field]:
                    try:
                        date_str = data[field].replace('Z', '+00:00')
                        data[field] = datetime.fromisoformat(date_str)
                    except (ValueError, AttributeError):
                        pass
            
            logger.info(f"UserUpdateSuperAdminUserView data: {data}")
            
            serializer = api_serializers.UserSaveUserRequestSerializer(data=data)
            if not serializer.is_valid():
                logger.error(f"UserUpdateSuperAdminUserView validation errors: {serializer.errors}")
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "details": serializer.errors,
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_data = serializer.validated_data
            saved_user = update_super_admin_user(user_data)
            
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
            logger.error(f"UserView : UpdateSuperAdminUser : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class UserGetUserByIdView(APIView):
    """Get user by ID"""
    
    def get(self, request):
        try:
            logger.info("UserView : GetUser : Started")
            
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
            logger.error(f"UserView : GetUser : {str(e)}")
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
            logger.info("UserView : GetUser : Started")
            
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
            logger.error(f"UserView : GetUser : {str(e)}")
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
            logger.info("UserView : GetUser : Started")
            
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
            logger.error(f"UserView : UpdatePassword : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class UserGetAllUnAssignedTeacherView(APIView):
    """Lists teachers without an assigned center."""
    
    def get(self, request):
        try:
            logger.info("UserView : GetUnAssignedTeachers : Started")
            
            teachers = Teacher.objects.filter(center__isnull=True).order_by('id')
            
            # Convert to dict for serialization
            data = []
            for teacher in teachers:
                data.append({
                    'id': teacher.id,
                    'name': teacher.full_name,
                    'assigned': False,
                    'profile': teacher.picture,
                    'phoneNumber': teacher.phone_number
                })
            
            serializer = api_serializers.TeacherUnAssignedDetailSerializer(data, many=True)
            
            if data:
                return Response(
                    {
                        "status": True,
                        "data": serializer.data,
                        "message": "List of teachers",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "data": None,
                        "message": "List of teachers not found",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : GetUnAssignedTeachers : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

class UserSearchDataView(APIView):
    """Search data by type and query string"""
    
    def get(self, request):
        try:
            logger.info("UserView : SearchData : Started")
            
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
            logger.error(f"UserView : SearchData : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )


#---------------------------------------------------------
# Teacher Views
#---------------------------------------------------------

class TeacherLoginteacherPostView(APIView):
    """Authenticates a teacher using hashed password comparison."""
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        try:
            logger.info("UserView : LoginSuperAdmin : Started")
            
            name = request.data.get('name')
            password = request.data.get('password')
            
            if not name or not password:
                return Response(
                    {
                        "status": False,
                        "error": "Name and password are required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            teacher = login_teacher(name, password)
            
            if teacher:
                return Response(
                    {
                        "status": True,
                        "data": teacher,
                        "message": "Teacher Login successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Teacher doesn't exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : LoginTeacher : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class TeacherSaveteacherPostView(APIView):
    """Saves a teacher record with hashed password storage."""
    
    def post(self, request):
        try:
            logger.info("UserView : LoginSuperAdmin : Started")
            
            serializer = api_serializers.TeacherSaveTeacherRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            teacher_data = serializer.validated_data
            
            # Hash password
            if teacher_data.get('Password'):
                teacher_data['Password'] = hash_password(teacher_data['Password'])
            
            saved_teacher = save_teacher(teacher_data)
            
            if saved_teacher:
                response_serializer = api_serializers.TeacherDtoSerializer(saved_teacher)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Teacher save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Teacher doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : SaveTeacher : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )


#---------------------------------------------------------
# RegionalAdmin Views
#---------------------------------------------------------

class RegionaladminGetallregionaladminGetView(APIView):
    """Lists all regional admin records."""
    
    def get(self, request):
        try:
            logger.info("RegionalAdminView : GetAllMasterAdmin : Started")
            
            regional_admins = get_all_regional_admins()
            
            if regional_admins is not None and len(regional_admins) > 0:
                response_serializer = api_serializers.RegionalAdminDtoSerializer(regional_admins, many=True)
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
            logger.error(f"RegionalAdminView : GetAllRegionalAdmin : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class RegionaladminLoginregionaladminPostView(APIView):
    """Authenticates a regional admin using hashed password comparison."""
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        try:
            logger.info("UserView : LoginRegionalAdmin : Started")
            
            name = request.data.get('name')
            password = request.data.get('password')
            
            if not name or not password:
                return Response(
                    {
                        "status": False,
                        "error": "Name and password are required",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            regional_admin = login_regional_admin(name, password)
            
            if regional_admin:
                return Response(
                    {
                        "status": True,
                        "data": regional_admin,
                        "message": "Regional admin Login successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Regional admin doesn't exists",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"UserView : LoginRegionalAdmin : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

class RegionaladminSaveregionaladminPostView(APIView):
    """Saves a regional admin record with hashed password storage."""
    
    def post(self, request):
        try:
            logger.info("RegionalAdminView : SaveRegionalAdmin : Started")
            
            serializer = api_serializers.RegionalAdminSaveRegionalAdminRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": False,
                        "error": "Invalid parameters",
                        "code": status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            regional_admin_data = serializer.validated_data
            
            # Hash password
            if regional_admin_data.get('Password'):
                regional_admin_data['Password'] = hash_password(regional_admin_data['Password'])
            
            saved_regional_admin = save_regional_admin(regional_admin_data)
            
            if saved_regional_admin:
                response_serializer = api_serializers.RegionalAdminDtoSerializer(saved_regional_admin)
                return Response(
                    {
                        "status": True,
                        "data": response_serializer.data,
                        "message": "Regional admin save successfully",
                        "code": status.HTTP_200_OK
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "status": False,
                        "error": "Regional admin doesn't save",
                        "code": status.HTTP_404_NOT_FOUND
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"RegionalAdminView : SaveRegionalAdmin : {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": str(e),
                    "code": status.HTTP_501_NOT_IMPLEMENTED
                },
                status=status.HTTP_501_NOT_IMPLEMENTED
            )


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


#---------------------------------------------------------
# Dashboard Views
#---------------------------------------------------------

class DashboardGetclasscountbymonthGetView(APIView):
    """Returns class counts grouped by started month."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetAllVillage : Started")
            
            center_id = request.query_params.get('centerId')
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not center_id or not start_date or not end_date:
                return Response(
                    {"error": "centerId, startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_class_count_by_month(int(center_id), start_date, end_date)
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetClassCountByMonth : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGettotalgenterratiobycenteridGetView(APIView):
    """Returns student gender counts for a center."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetAllVillage : Started")
            
            center_id = request.query_params.get('centerId')
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not center_id or not start_date or not end_date:
                return Response(
                    {"error": "centerId, startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_total_gender_ratio_by_center_id(int(center_id), start_date, end_date)
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetTotalGenterRatioByCenterId : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGettotalstudentofclassGetView(APIView):
    """Returns total students for a center."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetTotalStudentOfClass : Started")
            
            center_id = request.query_params.get('centerId')
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not center_id or not start_date or not end_date:
                return Response(
                    {"error": "centerId, startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_total_student_of_class(int(center_id), start_date, end_date)
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetTotalStudentOfClass : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGetcenterdetailbymonthGetView(APIView):
    """Returns center details with class and student counts."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetCenterDetailByMonth : Started")
            
            center_id = request.query_params.get('centerId')
            month = request.query_params.get('month')
            year = request.query_params.get('year')
            
            if not center_id or not month or not year:
                return Response(
                    {"error": "centerId, month and year are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            result = get_center_detail_by_month(int(center_id), int(month), int(year))
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetCenterDetailByMonth : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGettotalbplGetView(APIView):
    """Returns total BPL students for optional center filter."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetTotalBpl : Started")
            
            center_id = request.query_params.get('centerId')
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not center_id or not start_date or not end_date:
                return Response(
                    {"error": "centerId, startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_total_bpl(int(center_id), start_date, end_date)
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetTotalBpl : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGettotalstudentcategoryofclassGetView(APIView):
    """Returns student category counts for optional center filter."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetTotalBpl : Started")
            
            center_id = request.query_params.get('centerId')
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not center_id or not start_date or not end_date:
                return Response(
                    {"error": "centerId, startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_total_student_category_of_class(int(center_id), start_date, end_date)
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetTotalStudentCategoryOfClass : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGetuserbyfilterGetView(APIView):
    """Lists students matching dashboard location filters."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetCenterDetailByMonth : Started")
            
            district_id = request.query_params.get('districtId', 0)
            vidhan_sabha_id = request.query_params.get('vidhanSabhaId', 0)
            panchayta_id = request.query_params.get('panchaytaId', 0)
            village_id = request.query_params.get('villageId', 0)
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not start_date or not end_date:
                return Response(
                    {"error": "startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_user_by_filter(
                int(district_id), int(vidhan_sabha_id), 
                int(panchayta_id), int(village_id), 
                start_date, end_date
            )
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetUserByFilter : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGettotalbplbyfilterGetView(APIView):
    """Returns BPL count for dashboard location filters."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetCenterDetailByMonth : Started")
            
            district_id = request.query_params.get('districtId', 0)
            vidhan_sabha_id = request.query_params.get('vidhanSabhaId', 0)
            panchayta_id = request.query_params.get('panchaytaId', 0)
            village_id = request.query_params.get('villageId', 0)
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not start_date or not end_date:
                return Response(
                    {"error": "startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_total_bpl_by_filter(
                int(district_id), int(vidhan_sabha_id), 
                int(panchayta_id), int(village_id), 
                start_date, end_date
            )
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetTotalBplByFilter : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGettotalgenderratiobyfilterGetView(APIView):
    """Returns gender counts for dashboard location filters."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetCenterDetailByMonth : Started")
            
            district_id = request.query_params.get('districtId', 0)
            vidhan_sabha_id = request.query_params.get('vidhanSabhaId', 0)
            panchayta_id = request.query_params.get('panchaytaId', 0)
            village_id = request.query_params.get('villageId', 0)
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not start_date or not end_date:
                return Response(
                    {"error": "startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_total_gender_ratio_by_filter(
                int(district_id), int(vidhan_sabha_id), 
                int(panchayta_id), int(village_id), 
                start_date, end_date
            )
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetTotalGenderRatioByFilter : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGettotalstudentcategoryofclassbyfilterGetView(APIView):
    """Returns category counts for dashboard location filters."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetCenterDetailByMonth : Started")
            
            district_id = request.query_params.get('districtId', 0)
            vidhan_sabha_id = request.query_params.get('vidhanSabhaId', 0)
            panchayta_id = request.query_params.get('panchaytaId', 0)
            village_id = request.query_params.get('villageId', 0)
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not start_date or not end_date:
                return Response(
                    {"error": "startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_total_student_category_of_class_by_filter(
                int(district_id), int(vidhan_sabha_id), 
                int(panchayta_id), int(village_id), 
                start_date, end_date
            )
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetTotalStudentCategoryOfClassByFilter : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGettotalstudengradeofclassbyfilterGetView(APIView):
    """Returns grade counts for dashboard location filters."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetCenterDetailByMonth : Started")
            
            district_id = request.query_params.get('districtId', 0)
            vidhan_sabha_id = request.query_params.get('vidhanSabhaId', 0)
            panchayta_id = request.query_params.get('panchaytaId', 0)
            village_id = request.query_params.get('villageId', 0)
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not start_date or not end_date:
                return Response(
                    {"error": "startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_total_student_grade_of_class_by_filter(
                int(district_id), int(vidhan_sabha_id), 
                int(panchayta_id), int(village_id), 
                start_date, end_date
            )
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetTotalStudenGradetOfClassByFilter : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGetdistrictofcenterbyfilterGetView(APIView):
    """Lists centers matching district and Vidhan Sabha dashboard filters."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetCenterDetailByMonth : Started")
            
            district_id = request.query_params.get('districtId', 0)
            vidhan_sabha_id = request.query_params.get('vidhanSabhaId', 0)
            start_date = request.query_params.get('startDate')
            end_date = request.query_params.get('endDate')
            
            if not start_date or not end_date:
                return Response(
                    {"error": "startDate and endDate are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = parse_any_datetime(start_date)
            end_date = parse_any_datetime(end_date)
            
            result = get_district_of_center_by_filter(
                int(district_id), int(vidhan_sabha_id), 
                start_date, end_date
            )
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetDistrictOfCenterByFilter : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardGetstudentattendancebypercentageGetView(APIView):
    """Returns overall attendance percentage across students."""
    
    def get(self, request):
        try:
            logger.info("VillageView : GetStudentAttendanceByPercentage : Started")
            
            result = get_student_attendance_by_percentage()
            
            return Response(json.loads(result), status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DashboardView : GetStudentAttendanceByPercentage : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

#---------------------------------------------------------
# WeatherForecast Views
#---------------------------------------------------------

class WeatherforecastGetView(APIView):
    """Keeps the default .NET WeatherForecast sample route available."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            summaries = ["Freezing", "Bracing", "Chilly", "Cool", "Mild", "Warm", "Balmy", "Hot", "Sweltering", "Scorching"]
            import random
            
            result = []
            for i in range(1, 6):
                result.append({
                    "date": (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d'),
                    "temperatureC": random.randint(-20, 55),
                    "temperatureF": 0,
                    "summary": random.choice(summaries)
                })
            
            # Calculate Fahrenheit
            for item in result:
                item["temperatureF"] = int(32 + (item["temperatureC"] * 9 / 5))
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"WeatherForecastView : GetWeatherForecast : {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )