"""Tiny environment helpers, so settings stay readable without a heavy dep.

Every variable Django reads is prefixed, so `env_str("SITE_NAME")` reads
FINEXITO_SITE_NAME and the environment says plainly what belongs to us.
"""

import os

PREFIX = "FINEXITO_"
TRUTHY = {"1", "true", "yes", "on"}


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(PREFIX + name, default)


def env_int(name: str, default: int = 0) -> int:
    raw = os.environ.get(PREFIX + name)
    return int(raw) if raw else default


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(PREFIX + name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUTHY


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(PREFIX + name)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]
