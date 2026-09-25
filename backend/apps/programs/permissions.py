from rest_framework import permissions
from rest_framework.exceptions import NotFound


class HasProgram(permissions.BasePermission):
    """Requires the request to have resolved to an active program."""

    def has_permission(self, request, view) -> bool:
        if getattr(request, "program", None) is None:
            raise NotFound("No program resolved for this request. Send an X-Program header.")
        return True


class ProgramAppEnabled(permissions.BasePermission):
    """Guards a feature behind Program.enabled_apps.

    Set ``program_app = "store"`` on the view to use it.
    """

    def has_permission(self, request, view) -> bool:
        app_label = getattr(view, "program_app", None)
        program = getattr(request, "program", None)
        if app_label is None or program is None:
            return True
        if not program.has_app(app_label):
            raise NotFound(f"The '{app_label}' app is not enabled for this program.")
        return True
