from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from review_radar import __version__
from review_radar.api.errors import install_error_handlers
from review_radar.api.routers import dashboard, releases, replies, reviews
from review_radar.config import Settings
from review_radar.container import build_container
from review_radar.log import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level, json=settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with build_container(settings) as container:
            app.state.container = container
            yield

    app = FastAPI(
        title="Review Radar",
        version=__version__,
        summary="Store review triage, release regressions and human-approved replies.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    install_error_handlers(app)
    for router in (dashboard.router, reviews.router, releases.router, replies.router):
        app.include_router(router, prefix="/api")
    return app
