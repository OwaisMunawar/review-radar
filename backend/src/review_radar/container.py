"""Composition root: the one place that picks concrete adapters for each port.

Built once per process (API lifespan or CLI command) and passed down
explicitly; nothing reaches for it as a global.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from review_radar.adapters.clock import SystemClock
from review_radar.adapters.db.read_model import SqlReadModel
from review_radar.adapters.db.repositories import SqlUnitOfWork
from review_radar.adapters.db.session import make_engine, make_sessions
from review_radar.adapters.llm.agents import ModelSuite, build_models
from review_radar.adapters.llm.embeddings import PydanticAiTextEmbedder, build_embedder
from review_radar.adapters.stores.app_store import (
    AppStoreConnectClient,
    AppStoreConnectSource,
    AppStoreCredentials,
)
from review_radar.adapters.stores.fixture import FixtureSource
from review_radar.adapters.stores.google_play import (
    GooglePlayClient,
    GooglePlaySource,
    ServiceAccount,
)
from review_radar.adapters.stores.publisher import DryRunPublisher, StorePublisher
from review_radar.application.ingest import IngestReviews
from review_radar.application.pipeline import Pipeline
from review_radar.application.ports import ReplyPublisher, ReviewSource
from review_radar.application.releases import CompareReleases
from review_radar.application.replies import DraftReplies, PostReply, ReviewReply
from review_radar.application.themes import BuildThemes
from review_radar.application.triage import EmbedSummaries, TriageReviews
from review_radar.config import Settings
from review_radar.domain.models import Store


class UnitOfWorkFactory:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    def __call__(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self._sessions)


@dataclass(frozen=True, slots=True)
class StoreClients:
    app_store: AppStoreConnectClient | None
    google_play: GooglePlayClient | None


def build_store_clients(settings: Settings, http: httpx.AsyncClient) -> StoreClients:
    app_store = None
    pem = settings.app_store_key_pem()
    if settings.app_store_configured and pem:
        app_store = AppStoreConnectClient(
            app_id=str(settings.app_store_app_id),
            credentials=AppStoreCredentials(
                issuer_id=str(settings.app_store_issuer_id),
                key_id=str(settings.app_store_key_id),
                private_key_pem=pem,
            ),
            client=http,
        )
    google_play = None
    if settings.google_play_configured and settings.google_play_service_account_file:
        google_play = GooglePlayClient(
            package_name=str(settings.google_play_package_name),
            account=ServiceAccount.from_file(settings.google_play_service_account_file),
            client=http,
        )
    return StoreClients(app_store=app_store, google_play=google_play)


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    engine: AsyncEngine
    uow: UnitOfWorkFactory
    read: SqlReadModel
    models: ModelSuite
    embedder: PydanticAiTextEmbedder
    stores: StoreClients
    publisher: ReplyPublisher

    def live_sources(self) -> list[ReviewSource]:
        sources: list[ReviewSource] = []
        if self.stores.app_store:
            sources.append(AppStoreConnectSource(self.stores.app_store))
        if self.stores.google_play:
            sources.append(GooglePlaySource(self.stores.google_play))
        return sources

    def fixture_sources(self) -> list[ReviewSource]:
        return [FixtureSource(Store.APP_STORE), FixtureSource(Store.GOOGLE_PLAY)]

    def pipeline(self, sources: list[ReviewSource]) -> Pipeline:
        s = self.settings
        return Pipeline(
            ingest=IngestReviews(self.uow, sources),
            triage=TriageReviews(
                self.uow,
                self.models.triager,
                concurrency=s.triage_concurrency,
                attempts=s.llm_max_attempts,
            ),
            embed=EmbedSummaries(self.uow, self.embedder),
            themes=BuildThemes(self.uow, self.models.theme_namer, attempts=s.llm_max_attempts),
            draft=DraftReplies(
                self.uow,
                self.models.reply_writer,
                SystemClock(),
                concurrency=s.triage_concurrency,
                attempts=s.llm_max_attempts,
            ),
        )

    def compare_releases(self) -> CompareReleases:
        return CompareReleases(self.read)

    def review_reply(self) -> ReviewReply:
        return ReviewReply(self.uow, SystemClock())

    def post_reply(self) -> PostReply:
        return PostReply(self.uow, self.publisher, SystemClock())


@asynccontextmanager
async def build_container(settings: Settings) -> AsyncIterator[Container]:
    engine = make_engine(settings.database_url)
    sessions = make_sessions(engine)
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as http:
        stores = build_store_clients(settings, http)
        repliers = {
            store: client
            for store, client in (
                (Store.APP_STORE, stores.app_store),
                (Store.GOOGLE_PLAY, stores.google_play),
            )
            if client is not None
        }
        # Real posting needs keys and an explicit opt-in; anything less is a dry run.
        publisher: ReplyPublisher = (
            StorePublisher(repliers) if settings.posting_enabled and repliers else DryRunPublisher()
        )
        try:
            yield Container(
                settings=settings,
                engine=engine,
                uow=UnitOfWorkFactory(sessions),
                read=SqlReadModel(
                    sessions, model=settings.resolved_model, demo_mode=settings.demo_mode
                ),
                models=build_models(settings.resolved_model),
                embedder=build_embedder(settings.resolved_embedding_model),
                stores=stores,
                publisher=publisher,
            )
        finally:
            await engine.dispose()
