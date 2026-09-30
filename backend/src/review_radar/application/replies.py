"""Reply drafting and the approval workflow.

Drafting is automatic; everything after it needs a named human. Posting holds
a row lock across the store call so two clicks on "post" cannot double-post.
"""

import asyncio
from uuid import UUID, uuid4

import structlog

from review_radar.application.ports import Clock, ReplyPublisher, ReplyWriter, UnitOfWorkFactory
from review_radar.application.retry import with_retries
from review_radar.domain.errors import LlmError, NotFoundError
from review_radar.domain.models import LlmUsage, StoredReview
from review_radar.domain.replies import (
    REPLY_LIMITS,
    AuditEntry,
    Reply,
    ReplyAction,
    ReplyState,
    apply,
    next_state,
    validate_reply_body,
)

log = structlog.get_logger(__name__)


class DraftReplies:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        writer: ReplyWriter,
        clock: Clock,
        *,
        concurrency: int = 8,
        attempts: int = 3,
    ) -> None:
        self._uow = uow
        self._writer = writer
        self._clock = clock
        self._concurrency = concurrency
        self._attempts = attempts

    async def __call__(self, *, limit: int = 100) -> int:
        async with self._uow() as uow:
            reviews = await uow.reviews.list_without_reply(limit)
        semaphore = asyncio.Semaphore(self._concurrency)

        async def one(review: StoredReview) -> tuple[StoredReview, str, LlmUsage] | None:
            triage = review.triage
            if triage is None:  # list_without_reply only returns triaged reviews
                return None
            limit = REPLY_LIMITS[review.store]
            async with semaphore:
                try:
                    body, usage = await with_retries(
                        lambda: self._writer.write(review, triage, limit), attempts=self._attempts
                    )
                    return review, validate_reply_body(review.store, body), usage
                except LlmError as exc:
                    log.error("reply.draft_failed", review_id=str(review.id), error=exc.message)
                    return None

        drafted = [d for d in await asyncio.gather(*(one(r) for r in reviews)) if d is not None]
        now = self._clock.now()
        async with self._uow() as uow:
            for review, body, usage in drafted:
                reply = Reply(
                    id=uuid4(),
                    review_id=review.id,
                    store=review.store,
                    state=ReplyState.DRAFT,
                    body=body,
                    drafted_body=body,
                    model_name=usage.model_name,
                    created_at=now,
                    updated_at=now,
                )
                await uow.replies.add(reply)
                await uow.replies.append_audit(
                    AuditEntry(
                        reply_id=reply.id,
                        action=ReplyAction.DRAFT,
                        from_state=None,
                        to_state=ReplyState.DRAFT,
                        actor=f"agent:{usage.model_name}",
                        at=now,
                    )
                )
                await uow.usage.record(usage, review_id=review.id)
            await uow.commit()
        return len(drafted)


class ReviewReply:
    """Approve, edit, reject or reopen a draft on behalf of a person."""

    def __init__(self, uow: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(
        self,
        reply_id: UUID,
        action: ReplyAction,
        *,
        actor: str,
        body: str | None = None,
        note: str | None = None,
    ) -> Reply:
        if action in (ReplyAction.POST, ReplyAction.DRY_RUN_POST, ReplyAction.DRAFT):
            raise ValueError(f"{action.value} is not a review action")
        async with self._uow() as uow:
            reply = await uow.replies.get(reply_id, for_update=True)
            if reply is None:
                raise NotFoundError("reply not found", details={"reply_id": str(reply_id)})
            updated, entry = apply(
                reply, action, actor=actor, at=self._clock.now(), body=body, note=note
            )
            await uow.replies.save(updated)
            await uow.replies.append_audit(entry)
            await uow.commit()
        return updated


class PostReply:
    def __init__(self, uow: UnitOfWorkFactory, publisher: ReplyPublisher, clock: Clock) -> None:
        self._uow = uow
        self._publisher = publisher
        self._clock = clock

    async def __call__(self, reply_id: UUID, *, actor: str) -> Reply:
        action = ReplyAction.DRY_RUN_POST if self._publisher.dry_run else ReplyAction.POST
        async with self._uow() as uow:
            reply = await uow.replies.get(reply_id, for_update=True)
            if reply is None:
                raise NotFoundError("reply not found", details={"reply_id": str(reply_id)})
            # Fail on an unapproved reply before touching the store API.
            next_state(reply.state, action)
            review = await uow.reviews.get(reply.review_id)
            if review is None:  # pragma: no cover - FK guarantees it
                raise NotFoundError("review not found")
            external_id = await self._publisher.publish(
                store=reply.store, review_external_id=review.external_id, body=reply.body
            )
            updated, entry = apply(
                reply,
                action,
                actor=actor,
                at=self._clock.now(),
                external_reply_id=external_id,
                note=None if external_id else "dry run: store keys or POSTING_ENABLED not set",
            )
            await uow.replies.save(updated)
            await uow.replies.append_audit(entry)
            await uow.commit()
        return updated
