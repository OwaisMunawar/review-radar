.PHONY: up down dev-db install lint typecheck test eval web-check e2e screenshots check

up:            ## Full stack with demo data on http://localhost:8080
	docker compose up --build

down:
	docker compose down

dev-db:        ## Just Postgres + pgvector on localhost:55432
	docker compose up -d db

install:
	cd backend && uv sync
	cd web && npm ci

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd web && npm run lint && npm run format:check

typecheck:
	cd backend && uv run mypy
	cd web && npm run typecheck

test:          ## Backend tests on real Postgres (testcontainers or TEST_DATABASE_URL)
	cd backend && uv run pytest --cov=review_radar.domain --cov=review_radar.application --cov-fail-under=90
	cd web && npm test

eval:          ## Triage accuracy, macro-F1 and confusion matrix (MODEL=... for a real model)
	cd backend && uv run review-radar eval --min-accuracy 0.85 --min-macro-f1 0.85 --out ../docs/evals/$(or $(MODEL),demo).json

e2e:           ## Playwright smoke test against a running stack
	cd web && npm run e2e

screenshots:
	cd web && PW_CHANNEL=chrome npm run screenshots

check: lint typecheck test eval
