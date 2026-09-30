from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from review_radar.adapters.db.tables import LlmCallRow
from review_radar.adapters.llm.agents import build_models
from review_radar.adapters.llm.embeddings import build_embedder
from review_radar.application.triage import EmbedSummaries, TriageReviews
from review_radar.domain.errors import LlmError
from review_radar.domain.models import LlmPurpose, LlmUsage, StoredReview, Triage
from tests.conftest import UowFactory
from tests.factories import incoming, triage


class FlakyTriager:
    """Fails the first `failures` calls for each review, then succeeds."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls: dict[object, int] = {}

    async def triage(self, review: StoredReview) -> tuple[Triage, LlmUsage]:
        self.calls[review.id] = self.calls.get(review.id, 0) + 1
        if self.calls[review.id] <= self.failures:
            raise LlmError("rate limited")
        return triage(), LlmUsage(LlmPurpose.TRIAGE, "fake", 100, 20, Decimal("0.0005"), 12)


async def seed(uow_factory: UowFactory, n: int) -> None:
    async with uow_factory() as uow:
        await uow.reviews.upsert_many([incoming(days=i) for i in range(n)])
        await uow.commit()


async def test_triage_batches_with_accounting(
    uow_factory: UowFactory, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await seed(uow_factory, 7)
    result = await TriageReviews(uow_factory, build_models("demo").triager, batch_size=3)()
    assert (result.triaged, result.failed) == (7, 0)

    async with sessions() as session:
        calls = await session.scalar(
            select(func.count()).select_from(LlmCallRow).where(LlmCallRow.purpose == "triage")
        )
    assert calls == 7

    embedded = await EmbedSummaries(uow_factory, build_embedder("demo"), batch_size=4)()
    assert embedded == 7
    assert await EmbedSummaries(uow_factory, build_embedder("demo"))() == 0


async def test_triage_retries_transient_failures(uow_factory: UowFactory) -> None:
    await seed(uow_factory, 2)
    triager = FlakyTriager(failures=2)
    result = await TriageReviews(uow_factory, triager, attempts=3, retry_delay=0)()
    assert result.triaged == 2
    assert set(triager.calls.values()) == {3}


async def test_triage_gives_up_without_looping_and_respects_limit(uow_factory: UowFactory) -> None:
    await seed(uow_factory, 3)
    result = await TriageReviews(
        uow_factory, FlakyTriager(failures=99), attempts=2, retry_delay=0
    )()
    assert (result.triaged, result.failed) == (0, 3)

    limited = await TriageReviews(uow_factory, FlakyTriager(failures=0), batch_size=2)(limit=1)
    assert limited.triaged == 1
