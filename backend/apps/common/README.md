# common

Shared building blocks for every other app. It has no tables of its own.

## Base models — `models.py`

| Class              | Gives you                                              |
| ------------------ | ------------------------------------------------------ |
| `UUIDModel`        | A UUID `id`, safe to expose without leaking counts     |
| `TimeStampedModel` | `created_at` (indexed), `updated_at`                   |
| `BaseModel`        | Both of the above, plus `extra`                        |

New models should extend `BaseModel` unless there is a reason not to.

## `extra` and typed accessors — `fields.py`

`extra` is a flat `string → string` JSON map for anything app-specific. The
code that owns a key decides what its value means. For the common types, declare
a typed accessor on the model instead of converting by hand:

```python
class Profile(BaseModel):
    nickname = ExtraCharField(default="")
    visits = ExtraIntField(default=0)
    newsletter = ExtraBoolField(default=False)
    last_seen = ExtraDateTimeField()        # aware datetimes, stored as ISO 8601

profile.newsletter = True                   # extra == {"newsletter": "true"}
profile.visits += 1
profile.save()
```

- A missing or unparseable value reads as the default, because `extra` can be
  written from outside.
- Assigning `None` removes the key.
- Assigning the wrong type raises `TypeError`. A `bool` doesn't count as an
  `int`.
- `key=` stores the value under a different name from the attribute.
- Nothing is saved until the instance is.

On the API side, `serializers.ExtraField` validates `extra` as a flat object of
strings. It rejects numbers and booleans instead of turning them into strings.

## Errors — `exceptions.py`

`exception_handler` is DRF's `EXCEPTION_HANDLER`. It gives every failure the
same envelope:

```json
{ "error": { "code": "invalid", "message": "Validation failed.", "fields": { "email": ["..."] } } }
```

Django `ValidationError` and `Http404` are converted first. To document this
envelope in a view's schema, use `serializers.ErrorSerializer`.

## Everything else

| File             | What                                                                 |
| ---------------- | -------------------------------------------------------------------- |
| `views.py`       | `GET /api/v1/site/` → `{"name": SITE_NAME}`, unauthenticated. The frontend reads the product name from here. |
| `apps.py`        | Titles the Django admin from `SITE_NAME`.                            |
| `pagination.py`  | `DefaultPagination`: 20 per page, `?page_size=` up to 100.           |
| `serializers.py` | `ExtraField`, `StrictCharField`, `ReadOnlyModelSerializer`, `ErrorSerializer` |
| `testing.py`     | `PlatformTestCase`: a user plus `authenticate()` for API tests.      |
