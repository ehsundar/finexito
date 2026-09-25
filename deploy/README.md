# Production

One Ubuntu server runs everything with Docker Compose, serving your domain
(`example.com` below):

```
Internet -> caddy :80/:443 -> /api/* -> backend  (Django, gunicorn :8000)
                           -> /*     -> frontend (Next standalone :3000) -> backend
                              db (Postgres 17, internal only, volume `finexito_pgdata`)
```

| File                    | What it is                                                     |
| ----------------------- | -------------------------------------------------------------- |
| `provision.sh`          | Fresh Ubuntu box -> running site. Run from your machine.        |
| `deploy.sh`             | On the server: pull `main`, rebuild, migrate, restart.          |
| `compose.yml`           | The stack.                                                     |
| `Caddyfile`             | HTTPS, `/api/*` split, `www` -> bare-domain redirect.           |
| `.env.example`          | Template for `deploy/.env`, which holds the secrets on the server only. |
| `backup.sh`, `finexito-backup.cron` | Nightly `pg_dump`, 14 days kept.                    |

## Setting up a server

Follow [`docs/ops/server-setup.md`](../docs/ops/server-setup.md): create the
server with your SSH key, point DNS at it, then `make provision`.

## Deploying

```bash
git push origin main
make deploy        # ssh myserver /opt/finexito/deploy/deploy.sh
make logs          # follow all services
```

## Everyday commands (on the server, in /opt/finexito/deploy)

```bash
docker compose ps
docker compose exec backend python manage.py createprogram <slug> --name "..." --apps profiles
docker compose exec db psql -U finexito finexito
```

## Backups

Nightly at 03:30 into `/var/backups/finexito` (log: `/var/log/finexito-backup.log`).
They share a disk with the database, so copy them off the box too. Restore:

```bash
docker compose exec -T db pg_restore -U finexito -d finexito --clean --if-exists < /var/backups/finexito/<file>.dump
```

## Changing the domain

Point the new domain's records at the server, then edit `SITE_ADDRESS`,
`PUBLIC_ORIGIN` and `DJANGO_ALLOWED_HOSTS` in `deploy/.env` and run
`docker compose up -d`. Raise `SECURE_HSTS_SECONDS` once HTTPS has been stable
for a while.
