.PHONY: dev test lint format fmt web-dev api-dev db-up db-down clean

dev:
	docker-compose up

db-up:
	docker-compose up -d postgres

db-down:
	docker-compose stop postgres

api-dev:
	cd apps/api && uv run uvicorn field_notes_api.main:app --reload --port 8000

web-dev:
	cd apps/web && npm run dev

test:
	uv run pytest -q

lint:
	uv run ruff check .
	cd apps/web && npm run typecheck

format fmt:
	uv run ruff format .
	uv run ruff check --fix .

clean:
	rm -rf .venv apps/web/node_modules apps/web/dist
