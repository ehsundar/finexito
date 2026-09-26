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
vercel.json The previous Vercel deployment, kept until it is retired.
```

`make install` sets both up; `make run` starts both through `vercel dev`.

## The model

| App                                             | What it owns                                          |
| ----------------------------------------------- | ----------------------------------------------------- |
| [`accounts`](backend/apps/accounts/README.md)   | **User**: identity, sign-in, email verification.      |
| [`profiles`](backend/apps/profiles/README.md)   | **Profile**: everything else about a person. One per user. |
| [`common`](backend/apps/common/README.md)       | Base models, `extra` accessors, the error envelope.   |

`User` stays deliberately thin; a display name, an avatar, or arbitrary
attributes go on the profile. Each app's README is the reference for its models
and endpoints: update it in the same change as the code.

## Adding a facility later

1. Build it as an app under `apps/` with its own `README.md`, add it to `LOCAL_APPS`.
2. Register its routes in `config/api.py`.
3. Anything that differs between deployments becomes a setting read from the
   environment in `config/settings.py`.

## Running it

```bash
make install
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
make db-up
make migrate
cd backend && uv run python manage.py createsuperuser
make run          # both services, with the bindings Vercel injects in production
```

`make run` needs the Vercel CLI. To run one side at a time instead, use
`make run-back` (Django on :8000) and `make run-front` (Next on :3000).

Postgres everywhere, including tests — `make db-up` starts one on port 5434
(5432 and 5433 are taken by other projects on this machine). `DATABASE_URL`
defaults to that container locally and is required on Vercel.

```bash
make test           # Django's own runner
make lint           # ruff, eslint and tsc
make fmt            # ruff format
make schema         # regenerate openapi.yml and the frontend's types
make schema-check   # fails if either is stale -- run this in CI
```

`config/test_runner.py` refuses to run the suite against a non-local database
host, so a stray `manage.py test` cannot build tables on Neon. Shared setUp
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
[profiles and members](backend/apps/profiles/README.md#api--apiv1), and
`site/` in [common](backend/apps/common/README.md#everything-else).

### Everything else

| Path            | Purpose                          |
| --------------- | -------------------------------- |
| `/api/admin/`   | Django admin                     |
| `/api/docs/`    | Swagger UI                       |
| `/api/schema/`  | OpenAPI schema                   |
| `/api/healthz/` | Health check                     |
| `/api/static/`  | Collected static files (CDN)     |

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

## Deploying to Vercel (previous setup)

A Vercel project auto-deploying from `main` on this repo.

Both services ship as one Vercel project, declared in `vercel.json`:

```json
{
  "services": {
    "frontend": { "root": "frontend", "framework": "nextjs", "bindings": [ ... ] },
    "backend":  { "root": "backend" }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "backend" } },
    { "source": "/(.*)",     "destination": { "service": "frontend" } }
  ]
}
```

This is why the whole restructure was worth it. Every deployment builds and ships
both services together, so a preview URL always has a frontend and a backend that
agree with each other — no version skew, and rollbacks are atomic.

The frontend reaches Django through a **service binding**, which injects
`BACKEND_INTERNAL_URL` pointing at the Django build *from the same deployment*.
Nothing hardcodes a hostname, and preview deployments call their own backend
rather than production. Internal calls skip the public CDN, firewall and
deployment protection.

The public `/api/(.*)` rewrite exists for the routes a browser genuinely needs:
`/api/docs/`, `/api/admin/`, `/api/schema/`, `/api/healthz/` and `/api/static/`.
Because it hands the whole `/api` namespace to Django, **the Next.js app must not
add Route Handlers under `app/api`** — the session routes live at `/auth/*`
instead.

Since both sides share one origin, **there is no CORS to configure**.

Vercel has zero-config Django support: it finds `manage.py`, reads
`WSGI_APPLICATION` to locate the entrypoint, runs `collectstatic` during the
build, serves `STATIC_ROOT` from the CDN, and runs Django as one Fluid Compute
function.

The database is the Neon store shared with `restoration-disaster`, but this
platform owns a separate database inside it called `ehsundar` — its `public`
schema was already taken by that project's Prisma tables. `DATABASE_NAME`
selects it, which leaves the integration-managed `DATABASE_URL` alone.

Isolating by `search_path` instead does **not** work here: Neon's pooled
endpoint rejects `options=-c search_path=...` as a startup parameter.

What the repo already sets up for this:

- `vercel.json` — the two services, the ingress order, and a 60s `maxDuration`
  on `config/wsgi.py` with tests excluded from the bundle.
- `[tool.vercel] entrypoint` in `backend/pyproject.toml` — pins the WSGI callable.
- `settings.py` — when `VERCEL=1`: `DEBUG` off, `DJANGO_SECRET_KEY` and
  `DATABASE_URL` required (loud failure rather than an insecure default), the
  deployment hostnames trusted in `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`,
  `CONN_MAX_AGE=0` and `sslmode=require` for pooled Postgres, HSTS and secure
  cookies on.
- WhiteNoise for `vercel dev` and `runserver`; the CDN serves static in production.

Once a custom domain is attached, add it to the environment so session-based
admin logins through it pass CSRF:

```bash
vercel env add DJANGO_ALLOWED_HOSTS production    # example.com
vercel env add CSRF_TRUSTED_ORIGINS production    # https://example.com
```

### Migrations

They are not run during the build — run them yourself against the deployed
database:

```bash
cd backend
vercel env pull --environment=production   # writes .env.local, loaded by settings.py
DATABASE_NAME=ehsundar uv run python manage.py migrate
```

The same applies to `createsuperuser` against production.

### Serverless constraints worth knowing

- **No persistent filesystem.** `MEDIA_ROOT` is local-only. `Profile.avatar_url`
  is a URL, so nothing uploads today; the first real upload needs Vercel Blob.
- **No background workers.** No Celery worker or `cron` daemon — use Vercel Cron
  hitting an endpoint, or Vercel Queues.
- **Use Neon's pooled connection string.** One function instance per concurrent
  request means direct connections exhaust Postgres quickly.
