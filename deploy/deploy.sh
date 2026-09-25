#!/usr/bin/env bash
# Runs on the server: pull main, pull the images CI built, migrate, restart.
# `make deploy`, provision.sh and the Deploy GitHub Action call it.
#
# The Action's SSH key is pinned to this script, so the command it asks for
# arrives in SSH_ORIGINAL_COMMAND:
#   sync-env  read KEY=value lines from stdin into deploy/.env, then stop.
#             Only the keys listed in `managed` are accepted.
#   deploy <tag>  redeploy with images tagged <tag> (the Action passes the commit).
#   anything else (or none) redeploys with the `latest` images.
set -euo pipefail
cd "$(dirname "$0")"

if [ "${SSH_ORIGINAL_COMMAND:-}" = "sync-env" ]; then
  managed=" DJANGO_SECRET_KEY RESEND_API_KEY "
  while IFS='=' read -r key value; do
    [ -n "$key" ] || continue
    case "$managed" in *" $key "*) ;; *) echo "ignoring unmanaged key: $key" >&2; continue ;; esac
    [ -n "$value" ] || { echo "empty value for $key" >&2; exit 1; }
    tmp=$(mktemp)
    grep -v "^$key=" .env >"$tmp" || true
    printf '%s=%s\n' "$key" "$value" >>"$tmp"
    install -m 600 "$tmp" .env && rm -f "$tmp"
    echo "set $key"
  done
  exit 0
fi

# Only the Action sends a tag, and it is always a commit SHA.
read -r cmd tag _ <<<"${SSH_ORIGINAL_COMMAND:-}" || true
if [ "${cmd:-}" = "deploy" ] && [ -n "${tag:-}" ]; then
  [[ "$tag" =~ ^[0-9a-f]{40}$ ]] || { echo "bad image tag: $tag" >&2; exit 1; }
  export IMAGE_TAG="$tag"
fi

git -C .. pull --ff-only
docker compose pull backend frontend
docker compose run --rm backend python manage.py migrate --noinput
docker compose up -d --remove-orphans
docker image prune -f >/dev/null
docker compose ps
