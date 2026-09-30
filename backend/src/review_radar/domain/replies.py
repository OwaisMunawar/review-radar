"""Reply lifecycle.

The whole point of this module is that nothing reaches a store without a named
person approving the exact text. Every transition goes through `apply`, which
returns both the new reply and the audit entry that must be written with it.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from review_radar.domain.errors import InvalidTransitionError, ReplyInvalidError
from review_radar.domain.models import Store


class ReplyState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    POSTED = "posted"
    WOULD_POST = "would_post"


class ReplyAction(StrEnum):
    DRAFT = "draft"
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    REDRAFT = "redraft"
    POST = "post"
    DRY_RUN_POST = "dry_run_post"


APPROVED_STATES = frozenset({ReplyState.APPROVED, ReplyState.EDITED})

_TRANSITIONS: dict[tuple[ReplyState, ReplyAction], ReplyState] = {
    (ReplyState.DRAFT, ReplyAction.APPROVE): ReplyState.APPROVED,
    (ReplyState.DRAFT, ReplyAction.EDIT): ReplyState.EDITED,
    (ReplyState.DRAFT, ReplyAction.REJECT): ReplyState.REJECTED,
    (ReplyState.APPROVED, ReplyAction.EDIT): ReplyState.EDITED,
    (ReplyState.EDITED, ReplyAction.EDIT): ReplyState.EDITED,
    (ReplyState.APPROVED, ReplyAction.REJECT): ReplyState.REJECTED,
    (ReplyState.EDITED, ReplyAction.REJECT): ReplyState.REJECTED,
    (ReplyState.REJECTED, ReplyAction.REDRAFT): ReplyState.DRAFT,
    (ReplyState.APPROVED, ReplyAction.POST): ReplyState.POSTED,
    (ReplyState.EDITED, ReplyAction.POST): ReplyState.POSTED,
    (ReplyState.APPROVED, ReplyAction.DRY_RUN_POST): ReplyState.WOULD_POST,
    (ReplyState.EDITED, ReplyAction.DRY_RUN_POST): ReplyState.WOULD_POST,
    # Demo approvals can be posted for real once store keys are configured.
    (ReplyState.WOULD_POST, ReplyAction.POST): ReplyState.POSTED,
}

# Published store limits for developer responses.
REPLY_LIMITS: dict[Store, int] = {
    Store.APP_STORE: 5970,
    Store.GOOGLE_PLAY: 350,
}


def next_state(state: ReplyState, action: ReplyAction) -> ReplyState:
    try:
        return _TRANSITIONS[(state, action)]
    except KeyError:
        raise InvalidTransitionError(
            f"cannot {action.value} a reply that is {state.value}",
            details={"state": state.value, "action": action.value},
        ) from None


def allowed_actions(state: ReplyState) -> list[ReplyAction]:
    return [action for (from_state, action) in _TRANSITIONS if from_state == state]


def validate_reply_body(store: Store, body: str) -> str:
    text = body.strip()
    if not text:
        raise ReplyInvalidError("reply cannot be empty")
    limit = REPLY_LIMITS[store]
    if len(text) > limit:
        raise ReplyInvalidError(
            f"reply is {len(text)} characters; {store.value} allows {limit}",
            details={"length": len(text), "limit": limit},
        )
    return text


@dataclass(frozen=True, slots=True)
class Reply:
    id: UUID
    review_id: UUID
    store: Store
    state: ReplyState
    body: str
    drafted_body: str
    model_name: str
    created_at: datetime
    updated_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    posted_at: datetime | None = None
    external_reply_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditEntry:
    reply_id: UUID
    action: ReplyAction
    from_state: ReplyState | None
    to_state: ReplyState
    actor: str
    at: datetime
    note: str | None = None


def apply(
    reply: Reply,
    action: ReplyAction,
    *,
    actor: str,
    at: datetime,
    body: str | None = None,
    external_reply_id: str | None = None,
    note: str | None = None,
) -> tuple[Reply, AuditEntry]:
    target = next_state(reply.state, action)
    updated = replace(reply, state=target, updated_at=at)

    if action is ReplyAction.EDIT:
        if body is None:
            raise ReplyInvalidError("edit needs the new reply text")
        updated = replace(updated, body=validate_reply_body(reply.store, body))

    if target in APPROVED_STATES:
        # Editing counts as approving the edited text, so the approver is always
        # whoever last touched the words that will be posted.
        updated = replace(updated, approved_by=actor, approved_at=at)
    elif target is ReplyState.REJECTED or target is ReplyState.DRAFT:
        updated = replace(updated, approved_by=None, approved_at=None)
    elif target in (ReplyState.POSTED, ReplyState.WOULD_POST):
        # A reply is only postable once someone approved it; the transition
        # table already enforces that, and this guards against direct construction.
        if reply.approved_by is None:
            raise InvalidTransitionError("reply has no approver")
        updated = replace(updated, posted_at=at, external_reply_id=external_reply_id)

    entry = AuditEntry(
        reply_id=reply.id,
        action=action,
        from_state=reply.state,
        to_state=target,
        actor=actor,
        at=at,
        note=note,
    )
    return updated, entry
