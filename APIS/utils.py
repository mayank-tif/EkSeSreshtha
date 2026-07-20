import hashlib
import json
import re
import pandas as pd
from datetime import datetime
from .models import *
from django.urls import resolve
from rest_framework import status

import hashlib
from datetime import timedelta
from django.forms.models import model_to_dict
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken

from EkSeSreshtha.env_details import *
from .models import *

from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

SHA256_HEX_LENGTH = 64

import logging
logger = logging.getLogger(__name__)


def get_user_id_from_token(request):
    """
    Extract user ID from JWT token in the request header.
    Returns user_id if found, None otherwise.
    """
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None
        
        # Extract token from "Bearer <token>"
        parts = auth_header.split(' ')
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        
        token = parts[1]
        access_token = AccessToken(token)
        user_id = access_token.get('user_id')
        return user_id
        
    except (TokenError, InvalidToken, Exception) as e:
        logger.error(f"Error extracting user ID from token: {str(e)}")
        return None


# ==========Validate Mobile number function===============
def mobile_number_validation(mobileno):

    mobile_startwith = '6,7,8,9'
    mobile_length = 10

    regex = re.compile('[@_!#$%^&*()<>?/}{~:.+=`?,;"| ]')
    if pd.isnull(mobileno) or mobileno == '':
        return 'mobile number should not be empty..!'
    elif not mobileno.isdigit():
        return 'Please give only numbers.'
    elif not mobileno.startswith(tuple(mobile_startwith)):
        return 'mobile number should start with {}..!'.format(mobile_startwith)
    elif regex.search(mobileno) is not None:
        return 'mobile number should not contain any special character (@_!#$%^&*()<>?/}{~:.+=`?,;"| )'
    elif len(mobileno) < mobile_length:
        return 'mobile number length not less than {}..!'.format(mobile_length)
    elif len(mobileno) > mobile_length:
        return 'mobile number length not greater than {}..!'.format(mobile_length)
    
    
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


from .date_utils import parse_any_datetime


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


# utils.py - Activity Log Functions

def get_ip_address(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_activity(request, module, action, record_id=None, data=None):
    """Log user activity with request object"""
    try:
        user_id = get_user_id_from_token(request)
        ip_address = get_ip_address(request)
        
        # Convert data to JSON if it's a dict
        if data and isinstance(data, dict):
            import json
            data = json.dumps(data)
        
        ActivityLog.objects.create(
            user_id=user_id,
            module=module,
            action=action,
            record_id=record_id or 0,
            data=data,
            ip_address=ip_address,
            created_on=datetime.now()
        )
        logger.info(f"Activity logged: User {user_id} {action} {module} {record_id}")
    except Exception as e:
        logger.error(f"Failed to log activity: {str(e)}")

def log_activity_before(request, module, action, **kwargs):
    """Log activity at the start of a view"""
    try:
        user_id = get_user_id_from_token(request)
        ip_address = get_ip_address(request)
        
        data = {
            'url': request.path,
            'method': request.method,
            'params': dict(request.query_params),
            **kwargs
        }
        
        ActivityLog.objects.create(
            user_id=user_id,
            module=module,
            action=f"{action}_STARTED",
            record_id=0,
            data=json.dumps(data),
            ip_address=ip_address,
            created_on=datetime.now()
        )
        logger.info(f"Activity started: User {user_id} {action} {module}")
    except Exception as e:
        logger.error(f"Failed to log activity start: {str(e)}")