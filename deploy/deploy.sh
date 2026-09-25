#!/usr/bin/env bash
# Runs on the server: pull main, rebuild, migrate, restart. `make deploy` calls it.
set -euo pipefail
cd "$(dirname "$0")"

git -C .. pull --ff-only
docker compose build
docker compose run --rm backend python manage.py migrate --noinput
docker compose up -d --remove-orphans
docker image prune -f >/dev/null
docker compose ps
