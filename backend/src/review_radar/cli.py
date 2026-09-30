"""Command line entry point: `uv run review-radar --help`."""

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated

import typer

from review_radar.config import Settings
from review_radar.container import build_container
from review_radar.log import configure_logging

# The PydanticAI welcome banner is noise in scripted and container output.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Review Radar: triage store reviews, flag release regressions, draft replies.",
)
BACKEND = Path(__file__).resolve().parents[2]


def _settings() -> Settings:
    settings = Settings()
    configure_logging(settings.log_level, json=settings.log_json)
    return settings


@app.command()
def migrate() -> None:
    """Apply database migrations."""
    from alembic import command  # noqa: PLC0415 - keep CLI startup light
    from alembic.config import Config  # noqa: PLC0415

    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")


@app.command()
def seed(
    if_empty: Annotated[bool, typer.Option(help="Skip when reviews already exist.")] = False,
) -> None:
    """Load the synthetic Pocket Planner dataset and run the full pipeline on it."""

    async def run() -> None:
        async with build_container(_settings()) as container:
            if if_empty and (await container.read.overview(weeks=1)).total_reviews:
                typer.echo("database already has reviews; skipping seed")
                return
            report = await container.pipeline(container.fixture_sources()).run()
            typer.echo(report.model_dump_json(indent=2))

    asyncio.run(run())


@app.command()
def sync() -> None:
    """Ingest from the configured stores and run the pipeline on anything new."""

    async def run() -> None:
        async with build_container(_settings()) as container:
            sources = container.live_sources()
            if not sources:
                typer.echo("no store credentials configured; see .env.example", err=True)
                raise typer.Exit(code=2)
            report = await container.pipeline(sources).run()
            typer.echo(report.model_dump_json(indent=2))

    asyncio.run(run())


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
) -> None:
    """Run the API with uvicorn."""
    import uvicorn  # noqa: PLC0415

    uvicorn.run("review_radar.api.main:app", host=host, port=port, proxy_headers=True)


@app.command(name="eval")
def eval_triage(
    min_accuracy: Annotated[float, typer.Option(help="Fail below this category accuracy.")] = 0.0,
    min_macro_f1: Annotated[float, typer.Option(help="Fail below this category macro-F1.")] = 0.0,
    model: Annotated[str | None, typer.Option(help="Override MODEL for this run.")] = None,
    out: Annotated[Path | None, typer.Option(help="Write metrics as JSON.")] = None,
) -> None:
    """Score triage against the labelled set: accuracy, macro-F1, confusion matrix."""
    from review_radar.adapters.llm.agents import build_models  # noqa: PLC0415
    from review_radar.evals.triage_eval import render, run_triage_eval  # noqa: PLC0415

    settings = _settings()
    model_name = model or settings.resolved_model
    result = asyncio.run(run_triage_eval(build_models(model_name).triager, model_name=model_name))
    typer.echo(render(result))
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result.to_json(), indent=2) + "\n")
    if result.category.accuracy < min_accuracy or result.category.macro_f1 < min_macro_f1:
        typer.echo(
            f"\nbelow threshold: accuracy >= {min_accuracy:.2f}, macro-F1 >= {min_macro_f1:.2f}",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command()
def openapi(out: Annotated[Path | None, typer.Option(help="Write to a file.")] = None) -> None:
    """Print the OpenAPI schema (the web client generates its types from it)."""
    from review_radar.api.app import create_app  # noqa: PLC0415

    schema = json.dumps(create_app(Settings()).openapi(), indent=2) + "\n"
    if out:
        out.write_text(schema)
    else:
        typer.echo(schema)


if __name__ == "__main__":
    app()
