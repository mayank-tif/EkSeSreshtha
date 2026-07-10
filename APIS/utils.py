import hashlib
import re
import pandas as pd
from .models import *
import random
from datetime import datetime
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from django.urls import resolve
from rest_framework import status
from rest_framework.exceptions import APIException

class UnauthorizedValidationError(APIException):
    status_code = 401
    default_detail = "Unauthorized request due to validation error."
    default_code = "unauthorized_validation_error"

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
    
def validate_app_and_device_with_token(request):
    body_deviceid = request.data.get('deviceid')

    if not body_deviceid:
        raise ValidationError({"error": {"message": "DeviceID is not provided in body."}})

    # Extract JWT token from headers
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise AuthenticationFailed({"error": {"message":'JWT token not provided or invalid.'}})

    token = auth_header.split(' ')[1]  # Extract the token after 'Bearer'
    jwt_authenticator = JWTAuthentication()
    validated_token = jwt_authenticator.get_validated_token(token)

    # Compare email & device ID
    token_deviceid = validated_token.get('deviceid')

    if str(body_deviceid) != str(token_deviceid):
        raise UnauthorizedValidationError({"error": {"message":'DeviceID does not match with Token.'}})