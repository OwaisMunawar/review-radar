from collections.abc import AsyncIterator
from datetime import datetime

from review_radar.adapters.stores.fixture import FixtureSource
from review_radar.application.ingest import IngestReviews
from review_radar.domain.models import IncomingReview, Store
from tests.conftest import UowFactory
from tests.factories import incoming


class ListSource:
    def __init__(self, reviews: list[IncomingReview]) -> None:
        self.reviews = reviews

    @property
    def store(self) -> Store:
        return Store.GOOGLE_PLAY

    @property
    def name(self) -> str:
        return "list"

    async def fetch(self, *, since: datetime | None = None) -> AsyncIterator[IncomingReview]:
        for review in self.reviews:
            yield review


async def test_ingest_fixture_is_idempotent(uow_factory: UowFactory) -> None:
    ingest = IngestReviews(
        uow_factory,
        [FixtureSource(Store.APP_STORE), FixtureSource(Store.GOOGLE_PLAY)],
        batch_size=64,
    )
    first = await ingest()
    second = await ingest()
    assert (first.fetched, first.inserted, first.updated) == (400, 400, 0)
    assert (second.fetched, second.inserted, second.updated) == (400, 0, 0)


async def test_ingest_cleans_and_dedupes(uow_factory: UowFactory) -> None:
    dirty = incoming(external_id="d", rating=9, body="  hi  ", version="2.3.1 (512)")
    edited = incoming(external_id="d", rating=4, body="edited", version="2.3.1")
    result = await IngestReviews(uow_factory, [ListSource([dirty, edited])])()
    assert (result.fetched, result.inserted) == (2, 1)
    async with uow_factory() as uow:
        [stored] = await uow.reviews.list_untriaged(5)
    assert (stored.rating, stored.body, stored.app_version) == (4, "edited", "2.3.1")
