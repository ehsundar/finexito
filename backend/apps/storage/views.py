from django.conf import settings
from django.http import FileResponse, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.serializers import ErrorSerializer
from apps.storage import services
from apps.storage.backends import LocalStorage, check_signature
from apps.storage.models import StoredObject
from apps.storage.serializers import StoredObjectSerializer

# What a stored file may do once a browser opens it: nothing. Mirrors the
# public headers in deploy/Caddyfile.
FILE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
}


class UploadRefused(APIException):
    default_code = "upload_refused"

    def __init__(self, error: services.UploadError):
        self.status_code = error.status
        super().__init__(str(error))


class UploadView(APIView):
    """A LocalStorage upload link, signed like a presigned S3 PUT: whoever
    holds it PUTs the file's raw bytes to it, once, before the ticket expires."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        operation_id="storage_upload",
        request={"*/*": OpenApiTypes.BINARY},
        responses={
            200: None,
            **dict.fromkeys((400, 404, 409, 410, 411, 413, 415), ErrorSerializer),
        },
        description=(
            "Send the file as the raw body, with the Content-Type the ticket names "
            "and a Content-Length of exactly its size. Then POST `complete/`."
        ),
    )
    def put(self, request, pk):
        obj = StoredObject.objects.filter(pk=pk).first()
        if not (
            obj
            and isinstance(obj.backend, LocalStorage)
            and check_signature(
                obj,
                request.query_params.get("expires"),
                request.query_params.get("signature"),
                "upload",
            )
        ):
            raise NotFound()
        # Read straight from Django's request: DRF's request.data would buffer
        # and parse the whole body before any limit is checked.
        raw = request._request
        try:
            length = int(raw.META["CONTENT_LENGTH"]) if raw.META.get("CONTENT_LENGTH") else None
        except ValueError:
            length = None
        try:
            services.receive_upload(obj, raw, content_type=raw.content_type or "", length=length)
        except services.UploadError as error:
            raise UploadRefused(error) from error
        return Response(status=status.HTTP_200_OK)


class CompleteView(APIView):
    """Its owner says the file has been sent; it is checked and made ready."""

    @extend_schema(
        operation_id="storage_upload_complete",
        request=None,
        responses={
            200: StoredObjectSerializer,
            **dict.fromkeys((404, 409, 410, 413, 415), ErrorSerializer),
        },
    )
    def post(self, request, pk):
        obj = StoredObject.objects.filter(pk=pk, owner=request.user).first()
        if obj is None:
            raise NotFound()
        try:
            services.complete_upload(obj)
        except services.UploadError as error:
            raise UploadRefused(error) from error
        return Response(StoredObjectSerializer(obj).data)


@extend_schema(exclude=True)
class ObjectView(APIView):
    """A private LocalStorage object, opened through a signed link from
    ``services.object_url``.

    Behind Caddy the file never passes through Django: the response only names
    it in X-Accel-Redirect and Caddy sends it from the private directory.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request, pk):
        obj = StoredObject.objects.ready().filter(pk=pk).first()
        remaining = (
            obj
            and isinstance(obj.backend, LocalStorage)
            and not obj.backend.public
            and check_signature(
                obj,
                request.query_params.get("expires"),
                request.query_params.get("signature"),
                "object",
            )
        )
        if not remaining:
            raise NotFound()

        if settings.STORAGE_ACCEL_REDIRECT:
            response = HttpResponse(headers={"X-Accel-Redirect": f"/{obj.key}"})
        else:
            response = FileResponse(obj.backend.open(obj.key), content_type=obj.content_type)
        # Only for as long as the link is valid, and never in a shared cache.
        response["Cache-Control"] = f"private, max-age={remaining}"
        for header, value in FILE_HEADERS.items():
            response[header] = value
        return response
