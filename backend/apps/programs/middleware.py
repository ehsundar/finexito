"""Resolves the program a request belongs to.

Resolution order: the ``X-Program`` header, then a ``?program=`` query
parameter, then the request host, then ``DEFAULT_PROGRAM_SLUG``. The result is
attached as ``request.program`` and is ``None`` when nothing matches -- views
decide whether that is an error.
"""

from django.conf import settings

from apps.programs.models import Program, ProgramDomain


def _header_key(header_name: str) -> str:
    return "HTTP_" + header_name.upper().replace("-", "_")


def resolve_program(request) -> Program | None:
    slug = request.META.get(_header_key(settings.PROGRAM_HEADER)) or request.GET.get("program")
    if slug:
        return Program.objects.filter(slug=slug.strip().lower(), is_active=True).first()

    host = request.get_host().split(":")[0].lower()
    domain = (
        ProgramDomain.objects.select_related("program")
        .filter(host=host, program__is_active=True)
        .first()
    )
    if domain:
        return domain.program

    if settings.DEFAULT_PROGRAM_SLUG:
        return Program.objects.filter(slug=settings.DEFAULT_PROGRAM_SLUG, is_active=True).first()
    return None


class ProgramResolverMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Resolved eagerly: one indexed lookup per request, and callers can rely
        # on ``request.program is None`` meaning exactly that.
        request.program = resolve_program(request)
        return self.get_response(request)
