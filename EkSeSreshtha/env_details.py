import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_USERNAME = os.getenv('API_USERNAME')
API_PASSWORD = os.getenv('API_PASSWORD')
FI_API_USERNAME = os.getenv('FI_API_USERNAME')
FI_API_PASSWORD = os.getenv('FI_API_PASSWORD')

ATTENDANCE_ALLOWED_IPS = os.getenv('ATTENDANCE_ALLOWED_IPS', '')

# Attendance configuration
MANUAL_ATTENDANCE_MONTHLY_LIMIT = int(os.getenv('MANUAL_ATTENDANCE_MONTHLY_LIMIT', '30'))
ATTENDANCE_GPS_RADIUS_METERS = int(os.getenv('ATTENDANCE_GPS_RADIUS_METERS', '500'))

# Google Maps API
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
