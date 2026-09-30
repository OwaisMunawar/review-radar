"""Interfaces the use cases depend on. Adapters implement them; nothing here does IO.

Protocols rather than ABCs so fakes in tests and adapters in production need no
shared base class, and so mypy checks conformance structurally.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from review_radar.application.views import (
    OverviewView,
    Page,
    ReleaseSummaryView,
    ReplyView,
    ReviewFilters,
    ReviewView,
    ThemeView,
)
from review_radar.domain.models import (
    Category,
    IncomingReview,
    LlmUsage,
    Store,
    StoredReview,
    Triage,
)
from review_radar.domain.regression import ReleaseSample
from review_radar.domain.replies import AuditEntry, Reply, ReplyState
from review_radar.domain.trend import Trend

# --- Outbound: stores ---------------------------------------------------------


class ReviewSource(Protocol):
    """Anything that can list reviews for one app on one store."""

    @property
    def store(self) -> Store: ...

    @property
    def name(self) -> str: ...

    def fetch(self, *, since: datetime | None = None) -> AsyncIterator[IncomingReview]: ...


class ReplyPublisher(Protocol):
    @property
    def dry_run(self) -> bool: ...

    async def publish(self, *, store: Store, review_external_id: str, body: str) -> str | None:
        """Post a reply and return the store's id for it (None when dry-running)."""
        ...


# --- Outbound: models ---------------------------------------------------------


class ReviewTriager(Protocol):
    async def triage(self, review: StoredReview) -> tuple[Triage, LlmUsage]: ...


class ReplyWriter(Protocol):
    async def write(
        self, review: StoredReview, triage: Triage, limit: int
    ) -> tuple[str, LlmUsage]: ...


class ThemeNamer(Protocol):
    async def name(self, summaries: Sequence[str]) -> tuple[str, LlmUsage]: ...


class TextEmbedder(Protocol):
    @property
    def model_name(self) -> str: ...

    async def embed(self, texts: Sequence[str]) -> tuple[list[list[float]], LlmUsage]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


# --- Persistence --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UpsertResult:
    inserted: int
    updated: int


@dataclass(frozen=True, slots=True)
class EmbeddedSummary:
    review_id: UUID
    summary: str
    category: Category
    created_at: datetime
    vector: list[float]


@dataclass(frozen=True, slots=True)
class NewTheme:
    title: str
    dominant_category: Category
    trend: Trend
    weekly_counts: list[int]
    centroid: list[float]
    member_ids: list[UUID]
    representative_ids: list[UUID]


class ReviewRepository(Protocol):
    async def upsert_many(self, reviews: Sequence[IncomingReview]) -> UpsertResult: ...

    async def get(self, review_id: UUID) -> StoredReview | None: ...

    async def list_untriaged(self, limit: int) -> list[StoredReview]: ...

    async def list_without_reply(self, limit: int) -> list[StoredReview]: ...


class TriageRepository(Protocol):
    async def save(self, review_id: UUID, triage: Triage, model_name: str) -> None: ...

    async def list_missing_embeddings(self, limit: int) -> list[tuple[UUID, str]]: ...

    async def set_embeddings(self, vectors: Sequence[tuple[UUID, list[float]]]) -> None: ...

    async def list_embedded(self) -> list[EmbeddedSummary]: ...


class ThemeRepository(Protocol):
    async def replace_all(self, themes: Sequence[NewTheme]) -> list[UUID]: ...


class ReplyRepository(Protocol):
    async def add(self, reply: Reply) -> None: ...

    async def get(self, reply_id: UUID, *, for_update: bool = False) -> Reply | None: ...

    async def save(self, reply: Reply) -> None: ...

    async def append_audit(self, entry: AuditEntry) -> None: ...


class UsageRepository(Protocol):
    async def record(self, usage: LlmUsage, *, review_id: UUID | None = None) -> None: ...


class UnitOfWork(Protocol):
    """One transaction. Repositories share its session; nothing commits implicitly."""

    @property
    def reviews(self) -> ReviewRepository: ...

    @property
    def triages(self) -> TriageRepository: ...

    @property
    def themes(self) -> ThemeRepository: ...

    @property
    def replies(self) -> ReplyRepository: ...

    @property
    def usage(self) -> UsageRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...


class ReadModel(Protocol):
    """Query side for the dashboard. Read-only, so routers may call it directly."""

    async def overview(self, *, weeks: int) -> OverviewView: ...

    async def reviews(self, filters: ReviewFilters) -> Page[ReviewView]: ...

    async def review(self, review_id: UUID) -> ReviewView | None: ...

    async def similar_reviews(self, review_id: UUID, *, limit: int) -> list[ReviewView]: ...

    async def themes(self) -> list[ThemeView]: ...

    async def releases(self) -> list[ReleaseSummaryView]: ...

    async def release_samples(self) -> tuple[list[ReleaseSample], dict[str, str]]:
        """Per-version totals with category and theme counts, plus theme labels by key."""
        ...

    async def replies(
        self, *, state: ReplyState | None, store: Store | None, limit: int, offset: int
    ) -> Page[ReplyView]: ...

    async def reply(self, reply_id: UUID) -> ReplyView | None: ...
