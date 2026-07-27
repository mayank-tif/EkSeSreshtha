import logging

from django.db import IntegrityError
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get("request")
    view = context.get("view")

    logger.error(
        "API error in %s %s at %s",
        view.__class__.__name__ if view else "unknown view",
        request.method if request else "unknown method",
        request.get_full_path() if request else "unknown path",
        exc_info=True,
    )

    # Handle IntegrityError (e.g., duplicate entries)
    if isinstance(exc, IntegrityError):
        error_msg = str(exc)
        # Handle duplicate entry errors (MySQL error 1062)
        if '1062' in error_msg or 'Duplicate entry' in error_msg:
            # Extract the duplicate value from error message
            import re
            match = re.search(r"Duplicate entry '([^']+)'", error_msg)
            if match:
                duplicate_value = match.group(1)
                from rest_framework.response import Response
                from rest_framework import status
                return Response({
                    "status": False,
                    "error": f"{duplicate_value} already exists",
                    "code": status.HTTP_409_CONFLICT
                }, status=status.HTTP_409_CONFLICT)
            
            return Response({
                "status": False,
                "error": "This record already exists",
                "code": status.HTTP_409_CONFLICT
            }, status=status.HTTP_409_CONFLICT)
    
    return response
