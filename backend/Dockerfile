# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first so code changes do not invalidate the dependency layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build --chown=app /app/.venv /app/.venv
COPY --from=build --chown=app /app/alembic /app/alembic
COPY --from=build --chown=app /app/alembic.ini /app/alembic.ini
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYDANTIC_AI_NO_BANNER=1
USER app
EXPOSE 8000
CMD ["review-radar", "serve", "--host", "0.0.0.0", "--port", "8000"]
