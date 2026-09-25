#!/usr/bin/env bash
# Nightly pg_dump, run by /etc/cron.d/finexito-backup. Keeps 14 days.
# These live on the same disk as the database: copy them off-box for real safety.
set -euo pipefail
cd "$(dirname "$0")"

dest=/var/backups/finexito
mkdir -p "$dest"
docker compose exec -T db pg_dump -U finexito -Fc finexito >"$dest/finexito-$(date +%F).dump"
find "$dest" -name 'finexito-*.dump' -mtime +14 -delete
