"""
Date parsing utilities - separated to avoid circular imports.
"""
from datetime import datetime
from django.utils.dateparse import parse_date, parse_datetime


def parse_any_datetime(value):
    """
    Parse a datetime string in various formats.
    
    Supported formats:
    - ISO 8601: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD HH:MM:SS
    - DD-MM-YYYY, DD/MM/YYYY, DD-MM-YY, DD/MM/YY
    - DD-MM-YYYY HH:MM:SS, DD/MM/YYYY HH:MM:SS
    - DD-MM-YYYY HH:MM, DD/MM/YYYY HH:MM
    
    Returns datetime object or None if parsing fails.
    """
    if value in (None, ""):
        return None
    value_str = str(value).strip()
    
    # Try ISO formats first (ISO 8601)
    parsed = parse_datetime(value_str)
    if parsed:
        return parsed
    parsed_date = parse_date(value_str)
    if parsed_date:
        return parsed_date
    
    # Try DD-MM-YYYY or DD/MM/YYYY formats
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(value_str, fmt)
        except ValueError:
            continue
    
    # Try DD-MM-YYYY HH:MM:SS or DD/MM/YYYY HH:MM:SS
    for fmt in ("%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(value_str, fmt)
        except ValueError:
            continue
    
    return None