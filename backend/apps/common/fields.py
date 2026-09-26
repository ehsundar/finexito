"""Typed accessors over ``BaseModel.extra``."""

from datetime import datetime

from django.utils import timezone


class ExtraField:
    """A typed attribute stored as a string under one key of ``extra``.

    Declared on a model like a field, but it is not a column::

        class Profile(BaseModel):
            newsletter = ExtraBoolField(default=False)

        profile.newsletter = True   # extra == {"newsletter": "true"}
        profile.newsletter          # True

    Reads fall back to ``default`` when the key is missing or its value does not
    parse, since ``extra`` is writable from outside. Assigning ``None`` removes
    the key. Nothing is saved until the instance is.
    """

    python_type: type

    def __init__(self, default=None, *, key: str | None = None):
        self.default = default
        self.key = key

    def __set_name__(self, owner, name):
        self.key = self.key or name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        raw = instance.extra.get(self.key)
        if raw is None:
            return self.default
        try:
            return self.to_python(raw)
        except (TypeError, ValueError):
            return self.default

    def __set__(self, instance, value):
        if value is None:
            instance.extra.pop(self.key, None)
            return
        # bool is an int subclass; an int field must not accept True.
        if not isinstance(value, self.python_type) or (
            isinstance(value, bool) and self.python_type is not bool
        ):
            raise TypeError(f"{self.key} expects {self.python_type.__name__}, got {value!r}.")
        instance.extra[self.key] = self.to_string(value)

    def to_python(self, raw: str):
        raise NotImplementedError

    def to_string(self, value) -> str:
        return str(value)


class ExtraCharField(ExtraField):
    python_type = str

    def to_python(self, raw: str) -> str:
        return raw


class ExtraIntField(ExtraField):
    python_type = int

    def to_python(self, raw: str) -> int:
        return int(raw)


class ExtraBoolField(ExtraField):
    python_type = bool

    def to_python(self, raw: str) -> bool:
        if raw not in ("true", "false"):
            raise ValueError(raw)
        return raw == "true"

    def to_string(self, value: bool) -> str:
        return "true" if value else "false"


class ExtraDateTimeField(ExtraField):
    """ISO 8601. Aware datetimes only, so a stored value is never ambiguous."""

    python_type = datetime

    def to_python(self, raw: str) -> datetime:
        value = datetime.fromisoformat(raw)
        if timezone.is_naive(value):
            raise ValueError(raw)
        return value

    def to_string(self, value: datetime) -> str:
        if timezone.is_naive(value):
            raise ValueError(f"{self.key} needs a timezone-aware datetime.")
        return value.isoformat()
