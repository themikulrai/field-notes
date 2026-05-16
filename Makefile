.PHONY: dev test lint format fmt web-dev api-dev db-up db-down seed clean

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

# Seed the running API/DB with the prototype's mock data.
# Requires the API to be reachable at FIELD_NOTES_API_URL (default http://localhost:8000)
# and FIELD_NOTES_KEY to be set in the environment or .env file.
seed:
	uv run python -m tools.seed

clean:
	rm -rf .venv apps/web/node_modules apps/web/dist
