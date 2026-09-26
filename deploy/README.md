# Production

One Ubuntu server runs everything with Docker Compose, serving your domain
(`example.com` below):

```
Internet -> caddy :80/:443 -> /api/* -> backend  (Django, gunicorn :8000)
                           -> /*     -> frontend (Next standalone :3000) -> backend
                              db (Postgres 17, internal only, volume `finexito_pgdata`)
                              backup (nightly pg_dump to /var/backups/finexito)
                              uploads (volume `finexito_storage`, written by backend, served by caddy)
```

| File            | What it is                                                         |
| --------------- | ------------------------------------------------------------------ |
| `compose.yml`   | The whole stack, including migrations, health checks and backups.  |
| `Caddyfile`     | HTTPS, `/api/*` split, uploads, `www` -> bare-domain redirect.      |
| `.env.example`  | The keys of the server's `.env`, filled from GitHub on every deploy. |
| `render-env.sh` | Writes that `.env` from the GitHub secrets and variables.            |
| `provision.sh`  | Fresh Ubuntu box -> running site. Run from your machine.            |
| `server-setup.md` | Step-by-step guide to setting up a new server, start to finish.  |

## On the server

`/opt/finexito` holds three files and nothing else: `compose.yml` and
`Caddyfile`, copied on every deploy, and `.env`, which the Deploy Action
rewrites on every run from GitHub.
There is no git checkout and no build: the images come from CI.

## Deploying

Pushing to `main` deploys: CI tests, builds images tagged with the commit, then
runs `make deploy` for that commit. By hand, from your machine:

```bash
make deploy                        # the tip of origin/main (CI must have built it)
make deploy IMAGE_TAG=<older sha>  # roll back: CI's images for every commit stay in GHCR
make logs                          # follow all services
```

`make deploy` copies `compose.yml` and `Caddyfile` over, records `IMAGE_TAG` in
`.env`, pulls, and runs `docker compose up -d --wait`. The one-shot `migrate`
service runs first; the backend starts only once it succeeds, and `--wait`
fails the deploy unless backend and frontend report healthy.

Migrations run forwards only: rolling back restores the old code, not the old
schema, so keep migrations backwards-compatible with the release before them.
CI fails any push that edits or deletes a migration already on `main`.

## Settings and secrets

They live in GitHub, on the `production` environment: secrets for anything
sensitive (`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `RESEND_API_KEY`), variables
for the rest. On every run the Deploy Action writes `/opt/finexito/.env` from
them, taking each key listed in `.env.example`, so never edit the server's copy:
the next deploy overwrites it.

```bash
gh secret   set RESEND_API_KEY     --env production
gh variable set EMAIL_FROM_ADDRESS --env production --body no-reply@example.com
gh workflow run deploy.yml          # apply without a new commit
```

A new Django setting is a key in `.env.example` plus a secret or variable of the
same name. The backend receives every line of `.env`; the other containers get
only the few values they need, listed in `compose.yml`.

`POSTGRES_PASSWORD` must stay the one the database volume was created with.
Changing the secret does not change the database's password.

`make deploy` by hand reuses the `.env` the last Action run wrote.

## Everyday commands (on the server, in /opt/finexito)

```bash
docker compose ps
docker compose exec backend python manage.py createsuperuser
docker compose exec db psql -U finexito finexito
```

## Backups

Uploaded files live in the `finexito_storage` volume, not in the database
dumps. Browse them with `docker compose exec backend ls /srv/storage`, or copy
them off from the host at `/var/lib/docker/volumes/finexito_storage/_data`.
`docker compose down -v` deletes them along with the database. See
`backend/apps/storage/README.md`.

The `backup` service dumps the database nightly at 03:30 into
`/var/backups/finexito` and keeps 14 days. They share a disk with the database,
so copy them off the box too. Restore:

```bash
gunzip -c /var/backups/finexito/daily/<file>.sql.gz | docker compose exec -T db psql -U finexito finexito
```

## Changing the domain

Point the new domain's records at the server, then edit `SITE_ADDRESS`,
`PUBLIC_ORIGIN` and `DJANGO_ALLOWED_HOSTS` in GitHub and run the Deploy Action. Raise `SECURE_HSTS_SECONDS` once HTTPS has been stable for a
while.
