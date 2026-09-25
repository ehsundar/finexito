#!/usr/bin/env bash
# Runs on the server: pull main, rebuild, migrate, restart. `make deploy` and the
# Deploy GitHub Action call it.
#
# KEY=value lines on stdin overwrite those keys in deploy/.env first. The Action
# feeds DJANGO_SECRET_KEY this way, since its SSH key can run nothing but this
# script. Only the keys listed in `managed` are accepted.
set -euo pipefail
cd "$(dirname "$0")"

managed=" DJANGO_SECRET_KEY "
if [ ! -t 0 ]; then
  while IFS='=' read -r key value; do
    [ -n "$key" ] || continue
    case "$managed" in *" $key "*) ;; *) echo "ignoring unmanaged key: $key" >&2; continue ;; esac
    [ -n "$value" ] || { echo "empty value for $key" >&2; exit 1; }
    tmp=$(mktemp)
    grep -v "^$key=" .env >"$tmp" || true
    printf '%s=%s\n' "$key" "$value" >>"$tmp"
    install -m 600 "$tmp" .env && rm -f "$tmp"
    echo "set $key from stdin"
  done
fi

git -C .. pull --ff-only
docker compose build
docker compose run --rm backend python manage.py migrate --noinput
docker compose up -d --remove-orphans
docker image prune -f >/dev/null
docker compose ps
