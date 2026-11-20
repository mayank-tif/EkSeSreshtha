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
ATTENDANCE_SKIP_SUNDAY_CHECK = os.getenv('ATTENDANCE_SKIP_SUNDAY_CHECK', 'false').lower() == 'true'

# Google Maps API
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')

# Teacher leave: maximum allowed continuous working days
# (Sat/Sun and AcademicHoliday days are not counted). Leave beyond
# this limit is saved as 'pending' for SuperAdmin/RegionalAdmin approval.
TEACHERS_MAXIMUM_ALLOWED_HOLIDAYS = int(os.getenv('TEACHERS_MAXIMUM_ALLOWED_HOLIDAYS', '4'))

# Daily Class Report Scheduler logging
DAILY_CLASS_REPORT_SCHEDULE_LOGGER_NAME = os.getenv('DAILY_CLASS_REPORT_SCHEDULE_LOGGER_NAME', 'daily_class_report_scheduler_logs')
DAILY_CLASS_REPORT_SCHEDULE_LOGGING_LEVEL = os.getenv('DAILY_CLASS_REPORT_SCHEDULE_LOGGING_LEVEL', 'INFO')
DAILY_CLASS_REPORT_SCHEDULE_LOG_FILE_NAME = os.getenv('DAILY_CLASS_REPORT_SCHEDULE_LOG_FILE_NAME', 'daily_class_report_scheduler.log')
DAILY_CLASS_REPORT_SCHEDULE_LOG_FILE_FORMAT = os.getenv('DAILY_CLASS_REPORT_SCHEDULE_LOG_FILE_FORMAT', '%(asctime)s %(name)s - %(levelname)s - %(message)s')

# Daily Class Report Email Recipients
DAILY_CLASS_REPORT_TO_EMAILS = os.getenv('DAILY_CLASS_REPORT_TO_EMAILS', 'mayank@tiftechnologies.com')
DAILY_CLASS_REPORT_CC_EMAILS = os.getenv('DAILY_CLASS_REPORT_CC_EMAILS', '')
