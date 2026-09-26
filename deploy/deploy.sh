#!/usr/bin/env bash
# Brings up one release. Run by entry.sh from inside releases/<sha>/, with
# IMAGE_TAG set to that commit: pull CI's images, migrate, restart, and fail
# unless both apps answer, so entry.sh can put the previous release back.
set -euo pipefail
cd "$(dirname "$0")"
: "${IMAGE_TAG:?IMAGE_TAG must be set; deploy through /opt/finexito/bin/entry}"
export IMAGE_TAG

docker compose pull backend frontend
docker compose run --rm backend python manage.py migrate --noinput
docker compose up -d --remove-orphans

# Checked from inside the network, so neither DNS nor certificates get in the way.
answers() { docker compose exec -T caddy wget -q -O /dev/null "$1"; }
for _ in $(seq 30); do
  if answers http://backend:8000/api/healthz/ && answers http://frontend:3000/; then
    docker image prune -f >/dev/null
    docker compose ps
    exit 0
  fi
  sleep 2
done

echo "release $IMAGE_TAG did not become healthy" >&2
docker compose ps >&2
docker compose logs --tail=50 backend frontend >&2
exit 1
