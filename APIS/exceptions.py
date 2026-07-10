import logging

from rest_framework.views import exception_handler


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

    return response
