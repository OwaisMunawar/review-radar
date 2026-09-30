# Contributing

Thanks for taking a look. Issues and pull requests are welcome.

## Setup

You need Docker, [uv](https://docs.astral.sh/uv/) and Node 24.

```bash
make install     # uv sync + npm ci
make dev-db      # Postgres 16 + pgvector on localhost:55432
cd backend && uv run review-radar migrate && uv run review-radar seed
uv run review-radar serve          # API on :8000
cd ../web && npm run dev           # dashboard on :5173, proxies /api
```

## Before you open a pull request

```bash
make check       # ruff, mypy --strict, pytest with the coverage gate, eval threshold, web lint/types/tests
```

- Backend tests run against real Postgres. Locally they start a `pgvector/pgvector:pg16` container with testcontainers; set `TEST_DATABASE_URL` to use an existing database instead (it will be truncated).
- `domain/` and `application/` must stay at 90% line coverage or above. CI enforces it.
- If you change an API response model, run `npm run gen:api` in `web/` and commit the regenerated `src/api/schema.ts`.
- If you change prompts, rules or the triage schema, run `make eval` and include the before and after numbers in the PR description.
- Keep `domain/` free of IO and framework imports. New outbound dependencies get a `Protocol` in `application/ports.py` and an adapter.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `ci:`, `build:`, `chore:`), one logical change per commit, and every commit should pass `make check`.

## Data

The demo dataset and the eval set are fictional and written for this project. Please don't add real reviews scraped from the stores; they belong to their authors.
