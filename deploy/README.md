# Production

One Ubuntu server runs everything with Docker Compose, serving your domain
(`example.com` below):

```
Internet -> caddy :80/:443 -> /api/* -> backend  (Django, gunicorn :8000)
                           -> /*     -> frontend (Next standalone :3000) -> backend
                              db (Postgres 17, internal only, volume `finexito_pgdata`)
                              backup (nightly pg_dump to /var/backups/finexito)
```

| File            | What it is                                                         |
| --------------- | ------------------------------------------------------------------ |
| `compose.yml`   | The whole stack, including migrations, health checks and backups.  |
| `Caddyfile`     | HTTPS, `/api/*` split, `www` -> bare-domain redirect.               |
| `.env.example`  | Template for the server's `.env`, which holds the secrets there only. |
| `provision.sh`  | Fresh Ubuntu box -> running site. Run from your machine.            |

## On the server

`/opt/finexito` holds three files and nothing else: `compose.yml` and
`Caddyfile`, copied on every deploy, and `.env`, which only ever lives there.
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

The backend receives every line of `.env`, so a new Django setting is one line
there plus `make deploy`. The other containers get only the few values they need,
listed in `compose.yml`.

## Everyday commands (on the server, in /opt/finexito)

```bash
docker compose ps
docker compose exec backend python manage.py createsuperuser
docker compose exec db psql -U finexito finexito
```

## Backups

The `backup` service dumps the database nightly at 03:30 into
`/var/backups/finexito` and keeps 14 days. They share a disk with the database,
so copy them off the box too. Restore:

```bash
gunzip -c /var/backups/finexito/daily/<file>.sql.gz | docker compose exec -T db psql -U finexito finexito
```

## Changing the domain

Point the new domain's records at the server, then edit `SITE_ADDRESS`,
`PUBLIC_ORIGIN` and `DJANGO_ALLOWED_HOSTS` in `/opt/finexito/.env` and run
`make deploy`. Raise `SECURE_HSTS_SECONDS` once HTTPS has been stable for a
while.
