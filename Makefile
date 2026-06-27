.PHONY: dev build build-web restart stop status logs update test lint format fmt web-dev api-dev seed clean

# ---- Always-on local stack (Option B: native mamba Postgres + native uvicorn) ----

# Build the React app into apps/web/dist/ (served by the always-on API).
build:
	cd apps/web && npm run build

# Build the SPA AND stage it inside the API package so it ships in the wheel.
# Run this (on a machine with Node) before committing frontend changes or
# building a release — `uvx --from git+<repo> field-notes` serves this _web/.
#
# VITE_DEFAULT_KEY=local bakes a throwaway key into the local bundle so the UI
# skips the "enter your key" gate; the loopback server has auth disabled and
# ignores it. (A networked deploy builds its own dist without this.)
build-web:
	cd apps/web && npm ci && VITE_DEFAULT_KEY=local npm run build
	rm -rf apps/api/field_notes_api/_web
	cp -r apps/web/dist apps/api/field_notes_api/_web
	@echo "staged apps/web/dist -> apps/api/field_notes_api/_web (commit it so uvx-from-git serves the UI)"

# Restart the always-on API (after backend code changes or rebuilding the web).
restart:
	@PIDFILE=data/api.pid; \
	if [ -f $$PIDFILE ] && kill -0 $$(cat $$PIDFILE) 2>/dev/null; then \
	  echo "stopping API (pid $$(cat $$PIDFILE))..."; \
	  kill $$(cat $$PIDFILE); sleep 1; \
	fi; \
	/iris/u/mikulrai/bin/field-notes-api-start.sh; \
	sleep 2; \
	if curl -fs http://127.0.0.1:8000/healthz >/dev/null; then \
	  echo "API up on http://localhost:8000"; \
	else \
	  echo "API failed to start — check data/api.log"; exit 1; \
	fi

stop:
	@PIDFILE=data/api.pid; \
	if [ -f $$PIDFILE ] && kill -0 $$(cat $$PIDFILE) 2>/dev/null; then \
	  kill $$(cat $$PIDFILE); rm -f $$PIDFILE; echo "API stopped"; \
	else \
	  echo "API not running"; \
	fi

status:
	@PIDFILE=data/api.pid; \
	if [ -f $$PIDFILE ] && kill -0 $$(cat $$PIDFILE) 2>/dev/null; then \
	  echo "API: up (pid $$(cat $$PIDFILE))"; \
	else \
	  echo "API: down"; \
	fi; \
	if /iris/u/mikulrai/envs/field-notes-pg/bin/pg_ctl -D data/pgdata status >/dev/null 2>&1; then \
	  echo "Postgres: up"; \
	else \
	  echo "Postgres: down"; \
	fi

logs:
	tail -f data/api.log

# Pull, rebuild, migrate, restart. Use after `git pull`.
update:
	git pull
	cd apps/web && npm install && npm run build
	cd apps/api && uv run alembic upgrade head
	$(MAKE) restart

# ---- Developer hot-reload mode (only when actively coding) ----

# Hot-reload uvicorn (stops the always-on instance first; remember to `make restart` when done).
api-dev:
	$(MAKE) stop
	cd apps/api && uv run uvicorn field_notes_api.main:app --reload --port 8000

# Vite dev server with HMR; runs alongside the always-on API.
web-dev:
	cd apps/web && npm run dev

# ---- Misc ----

test:
	uv run pytest -q

lint:
	uv run ruff check .
	cd apps/web && npm run typecheck

format fmt:
	uv run ruff format .
	uv run ruff check --fix .

seed:
	uv run python -m tools.seed

clean:
	rm -rf .venv apps/web/node_modules apps/web/dist
