"""A single, predictable error envelope for every API response."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context) -> Response | None:
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        )
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    code = getattr(exc, "default_code", "error")
    detail = response.data
    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        message, fields = str(detail["detail"]), {}
    elif isinstance(detail, dict):
        message, fields = "Validation failed.", detail
    else:
        message, fields = "Request failed.", {"non_field_errors": detail}

    response.data = {"error": {"code": code, "message": message, "fields": fields}}
    return response
