.PHONY: install db-up db-down run run-back run-front test lint fmt migrate shell schema schema-check provision deploy rollback logs

# --- setup -----------------------------------------------------------------

install:
	cd backend && uv sync
	cd frontend && npm install

db-up:
	docker compose up -d db

db-down:
	docker compose down

# --- running ---------------------------------------------------------------

# Runs both services with the bindings Vercel would inject in production.
run:
	vercel dev

run-back:
	cd backend && uv run python manage.py runserver

run-front:
	cd frontend && npm run dev

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

# See deploy/README.md. `provision` takes a fresh Ubuntu box to a running site
# and is safe to re-run. `deploy` releases the tip of origin/main, whose images
# CI must already have built, so push and let CI finish first. `rollback` puts
# the previous release back.
DEPLOY_HOST ?= myserver
DOMAIN ?= example.com

provision:
	deploy/provision.sh $(DEPLOY_HOST) $(DOMAIN)

deploy:
	ssh $(DEPLOY_HOST) /opt/finexito/bin/entry release main

rollback:
	ssh $(DEPLOY_HOST) /opt/finexito/bin/entry rollback

logs:
	ssh $(DEPLOY_HOST) 'cd /opt/finexito/current && docker compose logs -f --tail=100'
