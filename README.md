# ehsundar

A shared Django REST backend, plus a Next.js frontend, for every app I host on
one server instance. Both live in this repository and deploy together to one
Hetzner box behind Caddy (see [Deploying](#deploying)). The
point is to write login, profiles, settings, and later OAuth, store and payments
**once**. Each app built on it is its own deployment, configured through Django
settings (environment variables), with its own database.

## Layout

```
backend/    Django + DRF. Owns data, auth and the OpenAPI schema.
frontend/   Next.js App Router. Owns the domain and every non-/api route.
openapi.yml Generated from the backend; the contract between the two.
deploy/     Production: Docker Compose stack, Caddy, provisioning and deploy scripts.
brand/      Logo, palette, type and voice; what a fork replaces to become a new product.
```

`make install` sets both up; `make run` starts both.

## The model

| App                                             | What it owns                                          |
| ----------------------------------------------- | ----------------------------------------------------- |
| [`accounts`](backend/apps/accounts/README.md)   | **User**: identity, Google sign-in, the system user.  |
| [`profiles`](backend/apps/profiles/README.md)   | **Profile**: everything else about a person. One per user. |
| [`content`](backend/apps/content/README.md)   | **Page**: public or private Markdown pages (a small CMS). |
| [`common`](backend/apps/common/README.md)       | Base models, `extra` accessors, the error envelope.   |

`User` stays deliberately thin; a display name, an avatar, or arbitrary
attributes go on the profile. Each app's README is the reference for its models
and endpoints: update it in the same change as the code.

## Adding a facility later

1. Build it as an app under `apps/` with its own `README.md`, add it to `LOCAL_APPS`.
2. Put its routes in the app's `urls.py`, full paths included; every installed
   app's `urls.py` is served under `/api/v1/`.
3. Anything that differs between deployments becomes a setting read from the
   environment in `config/settings.py`.

## Running it

```bash
make install
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
make db-up
make migrate
make run          # Django on :8000 and Next on :3000
```

Sign-in is Google only, locally too: the OAuth client needs
`http://localhost:3000/auth/google/callback` as an authorised redirect URI, and
`FINEXITO_ACCOUNTS_GOOGLE_CLIENT_ID` / `_SECRET` in `backend/.env`. To skip
Google, or to be someone else, `login_as` creates the account if needed and
prints a sign-in link (development only):

```bash
cd backend && uv run python manage.py login_as you@example.com
uv run python manage.py make_superuser you@example.com   # admin rights
```

To run one side at a time instead, use `make run-back` and `make run-front`.

Postgres everywhere, including tests — `make db-up` starts one on port 5434
(5432 and 5433 are taken by other projects on this machine). `FINEXITO_DATABASE_URL`
defaults to that container.

```bash
make test           # Django's own runner
make lint           # ruff, eslint and tsc
make fmt            # ruff format
make schema         # regenerate openapi.yml and the frontend's types
make schema-check   # fails if either is stale -- run this in CI
```

`config/test_runner.py` refuses to run the suite against a non-local database
host, so a stray `manage.py test` cannot build tables on a real server. Shared setUp
scaffolding lives in `apps/common/testing.py`.

Interactive API docs: <http://localhost:8000/api/docs/>.
Admin: <http://localhost:8000/api/admin/>.

Every route lives under `/api/` — admin, health check, docs and even the
collected static files. The frontend owns the rest of the domain (see
[Same-domain routing](#same-domain-routing)).

## API

All routes are under `/api/v1/`.

The endpoints are documented next to their code:
[auth](backend/apps/accounts/README.md#api--apiv1auth),
[profiles and members](backend/apps/profiles/README.md#api--apiv1),
[pages](backend/apps/content/README.md#api--apiv1), and
`site/` in [common](backend/apps/common/README.md#everything-else).

### Everything else

| Path            | Purpose                          |
| --------------- | -------------------------------- |
| `/api/admin/`   | Django admin                     |
| `/api/docs/`    | Swagger UI                       |
| `/api/schema/`  | OpenAPI schema                   |
| `/api/healthz/` | Health check                     |
| `/api/static/`  | Collected static files           |

## Errors

Every failure returns the same envelope:

```json
{ "error": { "code": "invalid", "message": "Validation failed.", "fields": { "email": ["..."] } } }
```

## The frontend

Next.js 16 (App Router) with Tailwind and shadcn/ui, in `frontend/`.

**The browser never talks to Django directly.** Tokens live in `httpOnly`
cookies, so no script on the page can read them, and every authenticated call is
made by the Next.js server, which attaches the `Authorization: Bearer` header
itself. Server Components fetch through `sessionApi()`; login, registration and
sign-out are Server Actions in `src/lib/auth/actions.ts`.

`src/proxy.ts` guards `/dashboard` and `/account` by looking at whether the
session cookies exist — an optimistic check, not authorisation; Django still
verifies every token. The access cookie's lifetime matches the token's, so when
it disappears the proxy sends the request to `/auth/refresh`, which rotates the
pair and returns the visitor to where they were. (`ROTATE_REFRESH_TOKENS` is on,
so the refresh token is replaced too, and both cookies are rewritten.)

### The typed client is the contract

`openapi.yml` is generated from the DRF serializers; `openapi-typescript` turns
it into `frontend/src/lib/api/schema.d.ts`, and `openapi-fetch` type-checks every
call against it. Change a serializer, run `make schema`, and any frontend code
that no longer matches **fails to compile** rather than breaking at runtime.

Both generated files are committed. `make schema-check` fails when they are
stale; run it in CI.

> A caveat worth knowing: openapi-fetch hands a `Request` object to `fetch`, and
> Next 16's instrumented fetch drops the body of a Request built that way — every
> POST arrives empty. `src/lib/api/client.ts` unwraps it back into
> `fetch(url, init)`. Retest on a Next upgrade; when it is fixed, that can go.

## Deploying

Production is one Ubuntu server running Docker Compose: Caddy (automatic HTTPS)
in front, Django under gunicorn, the Next.js standalone server and Postgres.
Everything needed to rebuild it from nothing lives in [`deploy/`](deploy/README.md):

```bash
make provision     # fresh Ubuntu box -> running site; safe to re-run
git push && make deploy
```

### Same-domain routing

Caddy sends `/api/*` to Django and everything else to Next.js, so both share one
origin and there is no CORS to configure in production. Because Django owns the
whole `/api` namespace, **the Next.js app must not add Route Handlers under
`app/api`**: the session routes live at `/auth/*` instead.
