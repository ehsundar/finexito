from django.core.exceptions import ValidationError as ModelValidationError
from django.http import HttpResponse
from django.utils.text import slugify
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.todos.projects.models import Project
from apps.todos.projects.serializers import ProjectSerializer
from apps.todos.projects.views import WriteThrottle
from apps.todos.templates import builtin
from apps.todos.templates.models import Template, apply, from_csv, snapshot, to_csv
from apps.todos.templates.serializers import (
    ApplyTemplateSerializer,
    SaveTemplateSerializer,
    TemplateSerializer,
)


def as_row(template) -> dict:
    mine = isinstance(template, Template)
    return {
        "id": str(template.pk) if mine else template.slug,
        "name": template.name,
        "description": template.description,
        "category": "Mine" if mine else template.category,
        "is_mine": mine,
        "task_count": sum(r["type"] == "task" for r in template.rows),
        "section_count": sum(r["type"] == "section" for r in template.rows),
    }


def csv_response(rows, name) -> HttpResponse:
    response = HttpResponse(to_csv(rows), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{slugify(name) or "template"}.csv"'
    return response


def model_errors(error: ModelValidationError):
    return ValidationError(getattr(error, "message_dict", None) or error.messages)


class TemplateViewSet(viewsets.ViewSet):
    """Built-in templates first, then the member's own."""

    throttle_classes = (WriteThrottle,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    lookup_value_regex = "[^/]+"

    def get_template(self, pk, mine=False):
        offered = {t.slug: t for t in builtin.BuiltIn.offered()}
        if pk in offered and not mine:
            return offered[pk]
        try:
            return Template.objects.get(pk=pk, owner=self.request.user)
        except (Template.DoesNotExist, ModelValidationError):
            raise NotFound() from None

    def project(self, pk):
        project = Project.objects.visible_to(self.request.user).filter(pk=pk).first()
        if project is None:
            raise NotFound()
        return project

    @extend_schema(responses=TemplateSerializer(many=True))
    def list(self, request):
        templates = [*builtin.BuiltIn.offered(), *Template.objects.filter(owner=request.user)]
        return Response(TemplateSerializer([as_row(t) for t in templates], many=True).data)

    @extend_schema(
        request={
            "application/json": SaveTemplateSerializer,
            "multipart/form-data": SaveTemplateSerializer,
        },
        responses={201: TemplateSerializer},
        description="Save a project as a template, or import a CSV file.",
    )
    def create(self, request):
        given = SaveTemplateSerializer(data=request.data)
        given.is_valid(raise_exception=True)
        data = given.validated_data
        try:
            if "project" in data:
                project = self.project(data["project"])
                rows, name = snapshot(project, request.user), project.name
            else:
                upload = data["file"]
                try:
                    text = upload.read().decode("utf-8-sig")
                except UnicodeDecodeError:
                    raise ValidationError({"file": "Save the file as UTF-8 CSV."}) from None
                rows, name = from_csv(text), upload.name.rsplit(".", 1)[0]
            template = Template(
                owner=request.user,
                name=data.get("name") or name,
                description=data.get("description", ""),
                rows=rows,
            )
            template.full_clean()
        except ModelValidationError as error:
            raise model_errors(error) from None
        template.save()
        return Response(TemplateSerializer(as_row(template)).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=TemplateSerializer)
    def retrieve(self, request, pk=None):
        return Response(TemplateSerializer(as_row(self.get_template(pk))).data)

    @extend_schema(request=TemplateSerializer, responses=TemplateSerializer)
    def partial_update(self, request, pk=None):
        template = self.get_template(pk, mine=True)
        given = TemplateSerializer(data=request.data, partial=True)
        given.is_valid(raise_exception=True)
        for name, value in given.validated_data.items():
            setattr(template, name, value)
        try:
            template.full_clean()
        except ModelValidationError as error:
            raise model_errors(error) from None
        template.save()
        return Response(TemplateSerializer(as_row(template)).data)

    @extend_schema(responses={204: None})
    def destroy(self, request, pk=None):
        self.get_template(pk, mine=True).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=ApplyTemplateSerializer,
        responses={201: ProjectSerializer},
        description="Create the template's sections and tasks in a new project, or at "
        "the end of `project`. Nothing is created if any of it breaks a limit.",
    )
    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        template = self.get_template(pk)
        given = ApplyTemplateSerializer(data=request.data)
        given.is_valid(raise_exception=True)
        target = given.validated_data.get("project")
        try:
            project = apply(
                template.rows,
                request.user,
                project=self.project(target) if target else None,
                name=given.validated_data.get("name") or template.name,
            )
        except ModelValidationError as error:
            raise model_errors(error) from None
        project = Project.objects.get(pk=project.pk)
        context = {"request": request}
        return Response(
            ProjectSerializer(project, context=context).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(responses={(200, "text/csv"): OpenApiTypes.STR})
    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        template = self.get_template(pk)
        return csv_response(template.rows, template.name)


class ProjectExportView(APIView):
    """A project's open sections and tasks as a template CSV file."""

    @extend_schema(responses={(200, "text/csv"): OpenApiTypes.STR})
    def get(self, request, pk):
        project = Project.objects.visible_to(request.user).filter(pk=pk).first()
        if project is None:
            raise NotFound()
        return csv_response(snapshot(project, request.user), project.name)
