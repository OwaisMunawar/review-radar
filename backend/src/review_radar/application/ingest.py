"""Pull reviews from every configured source and upsert them."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime

import structlog

from review_radar.application.ports import ReviewSource, UnitOfWorkFactory
from review_radar.domain.models import IncomingReview
from review_radar.domain.versions import normalize_version

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IngestResult:
    fetched: int
    inserted: int
    updated: int


class IngestReviews:
    def __init__(
        self, uow: UnitOfWorkFactory, sources: Sequence[ReviewSource], *, batch_size: int = 500
    ) -> None:
        self._uow = uow
        self._sources = sources
        self._batch_size = batch_size

    async def __call__(self, *, since: datetime | None = None) -> IngestResult:
        fetched = inserted = updated = 0
        for source in self._sources:
            batch: list[IncomingReview] = []
            async for review in source.fetch(since=since):
                batch.append(_clean(review))
                if len(batch) >= self._batch_size:
                    i, u = await self._flush(batch)
                    fetched, inserted, updated = fetched + len(batch), inserted + i, updated + u
                    batch = []
            if batch:
                i, u = await self._flush(batch)
                fetched, inserted, updated = fetched + len(batch), inserted + i, updated + u
            log.info("ingest.source_done", source=source.name, fetched=fetched)
        return IngestResult(fetched=fetched, inserted=inserted, updated=updated)

    async def _flush(self, batch: list[IncomingReview]) -> tuple[int, int]:
        # One transaction per batch: a failure halfway through a large backfill
        # keeps what was already stored, and re-running is safe because upserts
        # are keyed on (store, external_id).
        async with self._uow() as uow:
            result = await uow.reviews.upsert_many(_dedupe(batch))
            await uow.commit()
        return result.inserted, result.updated


def _clean(review: IncomingReview) -> IncomingReview:
    return replace(
        review,
        rating=min(5, max(1, review.rating)),
        body=review.body.strip(),
        app_version=normalize_version(review.app_version),
    )


def _dedupe(batch: list[IncomingReview]) -> list[IncomingReview]:
    """Keep the last copy of each review; Postgres rejects one upsert touching a row twice."""
    unique: dict[tuple[str, str], IncomingReview] = {}
    for review in batch:
        unique[(review.store.value, review.external_id)] = review
    return list(unique.values())
