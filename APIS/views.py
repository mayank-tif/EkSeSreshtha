from time import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import *
from django.http import HttpResponseForbidden
from django.conf import settings
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.permissions import IsAuthenticated
from EkSeSreshtha.env_details import *
from .models import *
from django.utils.timezone import now
from django.db.models import F
from .utils import token_validation_utils 
from datetime import datetime, timedelta
from django.utils.dateparse import parse_datetime


class DummyUser:
    def __init__(self, username):
        self.username = username
        self.id = 1

@method_decorator(csrf_exempt, name='dispatch')
class GenerateAppTokenView(TokenObtainPairView):
    serializer_class = GenerateAppTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        username = request.headers.get('Username')
        password = request.headers.get('Password')
        
        if (username != API_USERNAME or password != API_PASSWORD):
            return Response({'message': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer.is_valid(raise_exception=True)
        
        
        user = DummyUser(username)
        
        token = AccessToken.for_user(user)

        token['deviceid'] = request.data.get("deviceid")
        token['username'] = username
        token.set_exp(lifetime=timedelta(minutes=15))

        return Response({"access_token": str(token)}, status=status.HTTP_200_OK)
