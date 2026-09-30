from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from review_radar.adapters.db.read_model import SqlReadModel
from review_radar.adapters.llm.agents import build_models
from review_radar.adapters.stores.publisher import DryRunPublisher
from review_radar.application.replies import DraftReplies, PostReply, ReviewReply
from review_radar.domain.errors import InvalidTransitionError, LlmError, NotFoundError
from review_radar.domain.models import LlmUsage, Store, StoredReview, Triage
from review_radar.domain.replies import ReplyAction, ReplyState
from tests.conftest import UowFactory
from tests.factories import incoming, triage


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 1, 9, tzinfo=UTC)


class RecordingPublisher:
    def __init__(self) -> None:
        self.posted: list[tuple[Store, str, str]] = []

    @property
    def dry_run(self) -> bool:
        return False

    async def publish(self, *, store: Store, review_external_id: str, body: str) -> str | None:
        self.posted.append((store, review_external_id, body))
        return "store-reply-1"


class FailingWriter:
    async def write(self, review: StoredReview, triage: Triage, limit: int) -> tuple[str, LlmUsage]:
        raise LlmError("down")


async def drafted_reply(
    uow_factory: UowFactory, sessions: async_sessionmaker[AsyncSession]
) -> UUID:
    async with uow_factory() as uow:
        await uow.reviews.upsert_many([incoming(external_id="gp-1")])
        [review] = await uow.reviews.list_untriaged(1)
        await uow.triages.save(review.id, triage(), "demo")
        await uow.commit()
    drafted = await DraftReplies(uow_factory, build_models("demo").reply_writer, FixedClock())()
    assert drafted == 1
    page = await SqlReadModel(sessions, model="demo", demo_mode=True).replies(
        state=ReplyState.DRAFT, store=None, limit=10, offset=0
    )
    return page.items[0].id


async def test_approve_then_post_for_real(
    uow_factory: UowFactory, sessions: async_sessionmaker[AsyncSession]
) -> None:
    reply_id = await drafted_reply(uow_factory, sessions)
    review_reply = ReviewReply(uow_factory, FixedClock())
    publisher = RecordingPublisher()
    post = PostReply(uow_factory, publisher, FixedClock())

    with pytest.raises(InvalidTransitionError):
        await post(reply_id, actor="dana")
    assert publisher.posted == []

    approved = await review_reply(reply_id, ReplyAction.APPROVE, actor="dana")
    assert approved.approved_by == "dana"
    posted = await post(reply_id, actor="dana")
    assert posted.state is ReplyState.POSTED
    assert posted.external_reply_id == "store-reply-1"
    assert publisher.posted == [(Store.GOOGLE_PLAY, "gp-1", approved.body)]

    view = await SqlReadModel(sessions, model="demo", demo_mode=True).reply(reply_id)
    assert view is not None
    assert [a.action for a in view.audit] == [
        ReplyAction.DRAFT,
        ReplyAction.APPROVE,
        ReplyAction.POST,
    ]
    assert view.audit[0].actor == "agent:demo-rules"
    assert view.allowed_actions == []
    assert view.char_limit == 350


async def test_edit_reject_redraft_and_dry_run(
    uow_factory: UowFactory, sessions: async_sessionmaker[AsyncSession]
) -> None:
    reply_id = await drafted_reply(uow_factory, sessions)
    review_reply = ReviewReply(uow_factory, FixedClock())

    edited = await review_reply(reply_id, ReplyAction.EDIT, actor="sam", body="Fixed in 2.3.1.")
    assert (edited.state, edited.body) == (ReplyState.EDITED, "Fixed in 2.3.1.")
    rejected = await review_reply(reply_id, ReplyAction.REJECT, actor="sam", note="wrong fix")
    assert rejected.state is ReplyState.REJECTED
    reopened = await review_reply(reply_id, ReplyAction.REDRAFT, actor="sam")
    assert reopened.state is ReplyState.DRAFT
    await review_reply(reply_id, ReplyAction.APPROVE, actor="sam")

    would = await PostReply(uow_factory, DryRunPublisher(), FixedClock())(reply_id, actor="sam")
    assert would.state is ReplyState.WOULD_POST
    view = await SqlReadModel(sessions, model="demo", demo_mode=True).reply(reply_id)
    assert view is not None
    assert view.audit[-1].note is not None
    assert "dry run" in view.audit[-1].note


async def test_errors(uow_factory: UowFactory, sessions: async_sessionmaker[AsyncSession]) -> None:
    review_reply = ReviewReply(uow_factory, FixedClock())
    with pytest.raises(NotFoundError):
        await review_reply(uuid4(), ReplyAction.APPROVE, actor="x")
    with pytest.raises(NotFoundError):
        await PostReply(uow_factory, DryRunPublisher(), FixedClock())(uuid4(), actor="x")
    with pytest.raises(ValueError, match="not a review action"):
        await review_reply(uuid4(), ReplyAction.POST, actor="x")


async def test_failed_drafts_are_skipped(uow_factory: UowFactory) -> None:
    async with uow_factory() as uow:
        await uow.reviews.upsert_many([incoming()])
        [review] = await uow.reviews.list_untriaged(1)
        await uow.triages.save(review.id, triage(), "demo")
        await uow.commit()
    assert await DraftReplies(uow_factory, FailingWriter(), FixedClock(), attempts=1)() == 0
