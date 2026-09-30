"""Classify untriaged reviews, then embed their summaries."""

import asyncio
from dataclasses import dataclass

import structlog

from review_radar.application.ports import ReviewTriager, TextEmbedder, UnitOfWorkFactory
from review_radar.application.retry import with_retries
from review_radar.domain.errors import LlmError
from review_radar.domain.models import LlmUsage, StoredReview, Triage

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TriageResult:
    triaged: int
    failed: int


class TriageReviews:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        triager: ReviewTriager,
        *,
        concurrency: int = 8,
        attempts: int = 3,
        batch_size: int = 50,
        retry_delay: float = 0.5,
    ) -> None:
        self._uow = uow
        self._triager = triager
        self._concurrency = concurrency
        self._attempts = attempts
        self._batch_size = batch_size
        self._retry_delay = retry_delay

    async def __call__(self, *, limit: int | None = None) -> TriageResult:
        triaged = failed = 0
        remaining = limit
        # A review that fails every attempt stays untriaged; remembering it here
        # stops this run from fetching it again in an endless loop.
        skip: set[object] = set()
        while remaining is None or remaining > 0:
            size = self._batch_size if remaining is None else min(self._batch_size, remaining)
            async with self._uow() as uow:
                batch = [
                    r
                    for r in await uow.reviews.list_untriaged(size + len(skip))
                    if r.id not in skip
                ][:size]
            if not batch:
                break
            results = await self._run_batch(batch)
            async with self._uow() as uow:
                for review, outcome in zip(batch, results, strict=True):
                    if outcome is None:
                        skip.add(review.id)
                        failed += 1
                        continue
                    triage, usage = outcome
                    await uow.triages.save(review.id, triage, usage.model_name)
                    await uow.usage.record(usage, review_id=review.id)
                    triaged += 1
                await uow.commit()
            if remaining is not None:
                remaining -= len(batch)
            log.info("triage.batch", triaged=triaged, failed=failed)
        return TriageResult(triaged=triaged, failed=failed)

    async def _run_batch(self, batch: list[StoredReview]) -> list[tuple[Triage, LlmUsage] | None]:
        semaphore = asyncio.Semaphore(self._concurrency)

        async def one(review: StoredReview) -> tuple[Triage, LlmUsage] | None:
            async with semaphore:
                try:
                    return await with_retries(
                        lambda: self._triager.triage(review),
                        attempts=self._attempts,
                        base_delay=self._retry_delay,
                    )
                except LlmError as exc:
                    log.error("triage.failed", review_id=str(review.id), error=exc.message)
                    return None

        return await asyncio.gather(*(one(r) for r in batch))


class EmbedSummaries:
    def __init__(
        self, uow: UnitOfWorkFactory, embedder: TextEmbedder, *, batch_size: int = 128
    ) -> None:
        self._uow = uow
        self._embedder = embedder
        self._batch_size = batch_size

    async def __call__(self) -> int:
        embedded = 0
        while True:
            async with self._uow() as uow:
                pending = await uow.triages.list_missing_embeddings(self._batch_size)
            if not pending:
                return embedded
            vectors, usage = await self._embedder.embed([summary for _, summary in pending])
            async with self._uow() as uow:
                await uow.triages.set_embeddings(
                    [(rid, vec) for (rid, _), vec in zip(pending, vectors, strict=True)]
                )
                await uow.usage.record(usage)
                await uow.commit()
            embedded += len(pending)
