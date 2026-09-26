"""Test runner with a guard against building test tables on a remote database."""

from django.conf import settings
from django.test.runner import DiscoverRunner

LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1", "db"}


class SafeDiscoverRunner(DiscoverRunner):
    """Refuses to run anywhere but a local Postgres.

    A DATABASE_URL left pointing at a real server is what this guards against:
    a stray test run must never create tables there.
    """

    def setup_databases(self, **kwargs):
        host = settings.DATABASES["default"].get("HOST") or ""
        if host not in LOCAL_HOSTS:
            raise SystemExit(
                f"Refusing to run tests against the non-local database host {host!r}. "
                "Unset DATABASE_URL or point it at the docker compose database."
            )
        return super().setup_databases(**kwargs)
