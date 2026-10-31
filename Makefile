.PHONY: setup dev backend frontend db migrate revision test lint seed down types

UV ?= $(shell command -v uv 2>/dev/null || echo $(CURDIR)/.tools/bin/uv)
NPM ?= npm

setup:
	@test -f .env || cp .env.example .env
	@if [ ! -x "$(UV)" ]; then python3 -m venv .tools && .tools/bin/pip install -q uv; fi
	cd backend && $(UV) sync
	cd frontend && $(NPM) install
	docker compose up -d db mailpit

db:
	docker compose up -d db mailpit

dev: db
	./scripts/dev.sh

backend: db
	cd backend && $(UV) run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && $(NPM) run dev -- --host 127.0.0.1 --port 5173

migrate:
	cd backend && $(UV) run alembic upgrade head

revision:
	@test -n "$(msg)" || (echo 'Usage: make revision msg="describe the change"' && exit 1)
	cd backend && $(UV) run alembic revision --autogenerate -m "$(msg)"

test:
	cd backend && $(UV) run pytest

lint:
	cd backend && $(UV) run ruff check app tests
	cd frontend && $(NPM) run typecheck

seed:
	cd backend && $(UV) run python -m app.seed

types:
	cd backend && $(UV) run python -m app.export_openapi
	cd frontend && $(NPM) run generate-types

down:
	docker compose down
