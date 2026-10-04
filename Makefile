.PHONY: install db-up db-down run run-back run-front run-worker run-cron test lint fmt migrate shell schema schema-check provision deploy logs

# --- setup -----------------------------------------------------------------

install:
	cd backend && uv sync
	cd frontend && npm install

db-up:
	docker compose up -d db

db-down:
	docker compose down

# --- running ---------------------------------------------------------------

# Runs both services side by side; Ctrl-C stops both.
run:
	$(MAKE) -j2 run-back run-front

# On every interface, so a phone on the same network can reach it too.
run-back:
	cd backend && uv run python manage.py runserver 0.0.0.0:8000

run-front:
	cd frontend && npm run dev

# Background tasks (outgoing email and the like) wait in the database for these.
run-worker:
	cd backend && uv run python manage.py db_worker

# Fires due reminders every minute, as the cron container does in production.
run-cron:
	cd backend && while true; do uv run python manage.py fire_reminders; sleep 60; done

# --- the API contract ------------------------------------------------------

# The single source of truth for the frontend's types. Regenerate whenever a
# serializer, view or route changes, and commit the result: the frontend fails
# to typecheck rather than drifting silently.
schema:
	cd backend && uv run python manage.py spectacular --file ../openapi.yml
	cd frontend && npm run api:generate

# Fails when openapi.yml or the generated types are out of date. Run in CI.
schema-check: schema
	git diff --exit-code -- openapi.yml frontend/src/lib/api/schema.d.ts

# --- quality ---------------------------------------------------------------

test: db-up
	cd backend && uv run python manage.py test
	cd frontend && npm test

lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint
	cd frontend && npx tsc --noEmit

fmt:
	cd backend && uv run ruff format .

# --- django ----------------------------------------------------------------

migrate:
	cd backend && uv run python manage.py makemigrations && uv run python manage.py migrate

shell:
	cd backend && uv run python manage.py shell

# --- production (Hetzner) --------------------------------------------------

# See deploy/README.md. The server holds three files in /opt/finexito: the two
# below, copied on every deploy, and .env, which the Deploy Action writes from GitHub.
# `deploy` runs whatever IMAGE_TAG names (a commit CI has built; the tip of
# origin/main by default), so rolling back is `make deploy IMAGE_TAG=<older sha>`.
DEPLOY_HOST ?= hetzner
DOMAIN ?= ehsandar.dev
IMAGE_TAG ?= $(shell git rev-parse origin/main)

provision:
	deploy/provision.sh $(DEPLOY_HOST) $(DOMAIN)

deploy:
	scp -q deploy/compose.yml deploy/Caddyfile $(DEPLOY_HOST):/opt/finexito/
	ssh $(DEPLOY_HOST) 'set -e; cd /opt/finexito; \
	  sed -i "/^IMAGE_TAG=/d" .env; echo "IMAGE_TAG=$(IMAGE_TAG)" >> .env; \
	  install -d -o 999 -g 999 /var/backups/finexito; \
	  docker compose pull -q; \
	  docker compose up -d --wait --remove-orphans; \
	  docker image prune -f >/dev/null; docker compose ps'

logs:
	ssh $(DEPLOY_HOST) 'cd /opt/finexito && docker compose logs -f --tail=100'
