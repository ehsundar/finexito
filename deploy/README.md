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
| `entry.sh`              | The server's fixed entry point (`/opt/finexito/bin/entry`): `release`, `rollback`, `sync-env`. |
| `deploy.sh`             | Brings up one release: pull its images, migrate, restart, health-check. |
| `compose.yml`           | The stack.                                                     |
| `Caddyfile`             | HTTPS, `/api/*` split, `www` -> bare-domain redirect.           |
| `.env.example`          | Template for `shared/.env`, which holds the secrets on the server only. |
| `backup.sh`, `finexito-backup.cron` | Nightly `pg_dump`, 14 days kept.                    |

## Setting up a server

Follow [`docs/ops/server-setup.md`](../docs/ops/server-setup.md): create the
server with your SSH key, point DNS at it, then `make provision`.

## How a release works

There is no git checkout on the server, only this layout:

```
/opt/finexito/
  bin/entry          entry.sh; the CI key is pinned to it
  repo.git/          bare mirror of GitHub, fetched on every release
  shared/.env        secrets and site config, kept across releases
  releases/<sha>/    deploy/ from that commit, .env linked in (last 5 kept)
  current, previous  symlinks to the live release and the one before it
```

`entry release <sha>` fetches `main`, refuses any commit not on it, extracts
that commit's `deploy/` into `releases/<sha>/` and runs its `deploy.sh` with
the images CI built for that commit. `deploy.sh` migrates, restarts and waits
for both apps to answer. Only then does `current` move; if anything fails, the
previous release is brought back up. A successful release also installs its own
`entry.sh` and backup cron job, so changes to either ship like any other change.

Because the server fetches from GitHub itself and never keeps a working tree,
force-pushes to `main` deploy normally, and a leaked CI key can only release
commits that are already on `main`.

Migrations run forwards only. A rollback restores the old code, not the old
schema, so keep migrations backwards-compatible with the release before them.
CI fails any push that edits or deletes a migration already on `main`.

## Deploying

```bash
git push origin main   # CI tests, builds images and releases the commit
make deploy            # release the tip of main by hand (once CI has built it)
make rollback          # back to the previous release
make logs              # follow all services
```

## Everyday commands (on the server, in /opt/finexito/current)

```bash
docker compose ps
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
`PUBLIC_ORIGIN` and `DJANGO_ALLOWED_HOSTS` in `/opt/finexito/shared/.env` and
run `make deploy`. Raise `SECURE_HSTS_SECONDS` once HTTPS has been stable
for a while.
