from rest_framework import mixins, viewsets
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.permissions import AllowAny

from apps.content.models import Page, PageVisibility
from apps.content.serializers import PageSerializer, PageSummarySerializer


class PageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Published pages. Anyone may read public ones; private ones need a session."""

    permission_classes = (AllowAny,)
    lookup_field = "slug"
    filterset_fields = ("visibility",)

    def get_serializer_class(self):
        return PageSummarySerializer if self.action == "list" else PageSerializer

    def get_queryset(self):
        return Page.objects.visible_to(self.request.user)

    def get_object(self):
        page = Page.objects.published().filter(slug=self.kwargs["slug"]).first()
        if page is None:
            raise NotFound()
        if page.visibility == PageVisibility.PRIVATE and not self.request.user.is_authenticated:
            # Tells an anonymous visitor to sign in rather than pretending the
            # page is missing. Only the slug's existence leaks, never the content.
            raise NotAuthenticated("Sign in to read this page.")
        return page
