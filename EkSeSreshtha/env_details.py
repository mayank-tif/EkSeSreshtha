import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_USERNAME = os.getenv('API_USERNAME')
API_PASSWORD = os.getenv('API_PASSWORD')
FI_API_USERNAME = os.getenv('FI_API_USERNAME')
FI_API_PASSWORD = os.getenv('FI_API_PASSWORD')
