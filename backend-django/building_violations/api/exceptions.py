from rest_framework.response import Response
from rest_framework.views import exception_handler

from ..services.workflow import WorkflowError


def platform_exception_handler(exc, context):
    """Errors are returned as {"detail": "..."} like the rest of the MCG platform."""
    if isinstance(exc, WorkflowError):
        return Response({"detail": str(exc)}, status=exc.status)
    if isinstance(exc, ValueError):
        return Response({"detail": str(exc)}, status=400)
    return exception_handler(exc, context)
