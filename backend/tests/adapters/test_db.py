from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from review_radar.adapters.db.read_model import SqlReadModel
from review_radar.application.ports import NewTheme, ThemeLabel
from review_radar.application.views import ReviewFilters
from review_radar.domain.models import (
    EMBEDDING_DIMENSIONS,
    Category,
    LlmPurpose,
    LlmUsage,
    Sentiment,
    Store,
)
from review_radar.domain.replies import (
    Reply,
    ReplyAction,
    ReplyState,
    apply,
)
from review_radar.domain.trend import Trend
from tests.conftest import UowFactory
from tests.factories import BASE_TIME, incoming, triage


def unit(axis: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[axis] = 1.0
    return vector


async def test_upsert_is_idempotent_and_tracks_edits(uow_factory: UowFactory) -> None:
    first = incoming(external_id="same")
    async with uow_factory() as uow:
        assert (await uow.reviews.upsert_many([first, incoming()])).inserted == 2
        await uow.commit()

    edited = incoming(external_id="same", body="Fixed now, thanks!", rating=5, version=None)
    async with uow_factory() as uow:
        result = await uow.reviews.upsert_many([first, edited][1:])
        again = await uow.reviews.upsert_many([edited])
        await uow.commit()
    assert (result.inserted, result.updated) == (0, 1)
    assert (again.inserted, again.updated) == (0, 0)

    async with uow_factory() as uow:
        [row] = [r for r in await uow.reviews.list_untriaged(10) if r.external_id == "same"]
    assert row.rating == 5
    # A missing version on the edit keeps the version we already knew.
    assert row.app_version == "2.3.0"


async def test_same_id_on_two_stores_is_two_reviews(uow_factory: UowFactory) -> None:
    async with uow_factory() as uow:
        result = await uow.reviews.upsert_many(
            [incoming(external_id="x"), incoming(external_id="x", store=Store.APP_STORE)]
        )
        await uow.commit()
    assert result.inserted == 2


async def test_uncommitted_work_is_rolled_back(uow_factory: UowFactory) -> None:
    async with uow_factory() as uow:
        await uow.reviews.upsert_many([incoming()])
    async with uow_factory() as uow:
        assert await uow.reviews.list_untriaged(10) == []


async def test_triage_embeddings_and_similarity(
    uow_factory: UowFactory, sessions: async_sessionmaker[AsyncSession]
) -> None:
    async with uow_factory() as uow:
        await uow.reviews.upsert_many([incoming(days=i) for i in range(3)])
        reviews = await uow.reviews.list_untriaged(10)
        for review in reviews:
            await uow.triages.save(review.id, triage(), "demo")
        missing = await uow.triages.list_missing_embeddings(10)
        await uow.triages.set_embeddings(
            [(reviews[0].id, unit(0)), (reviews[1].id, unit(0)), (reviews[2].id, unit(1))]
        )
        await uow.commit()

    assert len(missing) == 3
    async with uow_factory() as uow:
        assert await uow.reviews.list_untriaged(10) == []
        embedded = await uow.triages.list_embedded()
        stored = await uow.reviews.get(reviews[0].id)
    assert [e.review_id for e in embedded] == [r.id for r in reviews]
    assert stored is not None
    assert stored.triage == triage()

    read = SqlReadModel(sessions, model="demo", demo_mode=True)
    similar = await read.similar_reviews(reviews[0].id, limit=2)
    assert [s.id for s in similar] == [reviews[1].id, reviews[2].id]
    assert await read.similar_reviews(uuid4(), limit=2) == []

    # Re-triage clears the stale embedding.
    async with uow_factory() as uow:
        await uow.triages.save(reviews[0].id, triage(category=Category.LOGIN), "demo")
        await uow.commit()
        assert [rid for rid, _ in await uow.triages.list_missing_embeddings(10)] == [reviews[0].id]


async def test_reply_constraints_and_append_only_audit(uow_factory: UowFactory) -> None:
    async with uow_factory() as uow:
        await uow.reviews.upsert_many([incoming()])
        [review] = await uow.reviews.list_untriaged(1)
        reply = Reply(
            id=uuid4(),
            review_id=review.id,
            store=review.store,
            state=ReplyState.DRAFT,
            body="Sorry about that.",
            drafted_body="Sorry about that.",
            model_name="demo",
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
        await uow.replies.add(reply)
        approved, entry = apply(reply, ReplyAction.APPROVE, actor="dana", at=BASE_TIME)
        await uow.replies.save(approved)
        await uow.replies.append_audit(entry)
        await uow.commit()

    async with uow_factory() as uow:
        loaded = await uow.replies.get(reply.id, for_update=True)
        assert loaded == approved
        assert await uow.replies.get(uuid4()) is None

    # The database refuses a posted reply without an approver, whatever the code does.
    async with uow_factory() as uow:
        forged = replace(reply, state=ReplyState.POSTED)
        with pytest.raises(IntegrityError):
            await uow.replies.save(forged)

    async with uow_factory() as uow:
        with pytest.raises(DBAPIError, match="append-only"):
            await uow._session.execute(text("UPDATE reply_audit SET actor = 'mallory'"))


async def test_themes_and_read_model(
    uow_factory: UowFactory, sessions: async_sessionmaker[AsyncSession]
) -> None:
    async with uow_factory() as uow:
        await uow.reviews.upsert_many(
            [
                incoming(version="2.2.0", days=-10, rating=5),
                incoming(),
                incoming(rating=1),
                incoming(store=Store.APP_STORE, version="2.10.0", days=5, body="Love it 100%"),
            ]
        )
        reviews = await uow.reviews.list_untriaged(10)
        for review in reviews[:3]:
            await uow.triages.save(review.id, triage(), "demo")
        await uow.triages.save(
            reviews[3].id,
            triage(Category.PRAISE, Sentiment.POSITIVE, summary="Great planner"),
            "demo",
        )
        await uow.usage.record(
            LlmUsage(LlmPurpose.TRIAGE, "demo", 10, 5, Decimal("0.0012"), 3),
            review_id=reviews[0].id,
        )
        [theme_id] = await uow.themes.replace_all(
            [
                NewTheme(
                    title="Crash on sign-in",
                    dominant_category=Category.CRASH,
                    trend=Trend.RISING,
                    weekly_counts=[0, 1, 2],
                    centroid=unit(0),
                    member_ids=[r.id for r in reviews[1:3]],
                    representative_ids=[reviews[1].id],
                )
            ]
        )
        await uow.commit()

    read = SqlReadModel(sessions, model="demo", demo_mode=True)
    overview = await read.overview(weeks=12)
    assert overview.total_reviews == 4
    assert overview.negative_share == pytest.approx(0.75)
    assert overview.stores == {Store.GOOGLE_PLAY: 3, Store.APP_STORE: 1}
    assert overview.usage.cost_usd == Decimal("0.0012")
    assert sum(w.reviews for w in overview.weekly) == 4
    assert overview.categories[0].category is Category.CRASH

    [theme] = await read.themes()
    assert theme.id == theme_id
    assert theme.negative_share == 1.0
    assert [r.id for r in theme.representatives] == [reviews[1].id]

    page = await read.reviews(ReviewFilters(theme_id=theme_id, limit=1))
    assert (page.total, len(page.items)) == (2, 1)
    assert page.items[0].theme_title == "Crash on sign-in"
    assert (await read.reviews(ReviewFilters(q="100%"))).total == 1
    assert (await read.reviews(ReviewFilters(q="100_"))).total == 0
    filtered = ReviewFilters(
        store=Store.GOOGLE_PLAY,
        category=Category.CRASH,
        sentiment=Sentiment.NEGATIVE,
        severity=triage().severity,
        version="2.3.0",
        rating=1,
    )
    assert (await read.reviews(filtered)).total == 1
    assert (await read.review(reviews[3].id)) is not None
    assert (await read.review(uuid4())) is None

    releases = await read.releases()
    assert [r.version for r in releases] == ["2.2.0", "2.3.0", "2.10.0"]

    samples, labels = await read.release_samples()
    by_version = {s.version: s for s in samples}
    assert by_version["2.3.0"].total == 2
    assert by_version["2.3.0"].counts == {"category:crash": 2, f"theme:{theme_id}": 2}
    assert labels == {f"theme:{theme_id}": ThemeLabel("Crash on sign-in", Category.CRASH)}

    async with uow_factory() as uow:
        assert await uow.themes.replace_all([]) == []
        await uow.commit()
    assert await read.themes() == []
    assert BASE_TIME + timedelta(days=5) == releases[-1].first_review_at
