from datetime import UTC, datetime
from uuid import uuid4

import pytest

from review_radar.domain.errors import InvalidTransitionError, ReplyInvalidError
from review_radar.domain.models import Store
from review_radar.domain.replies import (
    Reply,
    ReplyAction,
    ReplyState,
    allowed_actions,
    apply,
    next_state,
    validate_reply_body,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def make_reply(state: ReplyState = ReplyState.DRAFT, store: Store = Store.GOOGLE_PLAY) -> Reply:
    return Reply(
        id=uuid4(),
        review_id=uuid4(),
        store=store,
        state=state,
        body="Thanks for the report.",
        drafted_body="Thanks for the report.",
        model_name="demo",
        created_at=NOW,
        updated_at=NOW,
    )


def test_approve_then_post_records_approver_and_audit() -> None:
    approved, entry = apply(make_reply(), ReplyAction.APPROVE, actor="dana", at=NOW)
    assert approved.state is ReplyState.APPROVED
    assert approved.approved_by == "dana"
    assert (entry.from_state, entry.to_state) == (ReplyState.DRAFT, ReplyState.APPROVED)

    posted, entry = apply(approved, ReplyAction.POST, actor="dana", at=NOW, external_reply_id="r1")
    assert posted.state is ReplyState.POSTED
    assert posted.external_reply_id == "r1"
    assert posted.posted_at == NOW
    assert entry.action is ReplyAction.POST


def test_draft_cannot_be_posted() -> None:
    with pytest.raises(InvalidTransitionError) as caught:
        apply(make_reply(), ReplyAction.POST, actor="dana", at=NOW)
    assert caught.value.details == {"state": "draft", "action": "post"}


def test_edit_validates_and_counts_as_approval() -> None:
    edited, _ = apply(
        make_reply(), ReplyAction.EDIT, actor="sam", at=NOW, body="  Fixed in 2.3.1. "
    )
    assert edited.state is ReplyState.EDITED
    assert edited.body == "Fixed in 2.3.1."
    assert edited.drafted_body == "Thanks for the report."
    assert edited.approved_by == "sam"


def test_edit_requires_body() -> None:
    with pytest.raises(ReplyInvalidError):
        apply(make_reply(), ReplyAction.EDIT, actor="sam", at=NOW)


def test_reject_clears_approval_and_redraft_reopens() -> None:
    approved, _ = apply(make_reply(), ReplyAction.APPROVE, actor="dana", at=NOW)
    rejected, _ = apply(approved, ReplyAction.REJECT, actor="dana", at=NOW, note="off tone")
    assert rejected.approved_by is None
    reopened, entry = apply(rejected, ReplyAction.REDRAFT, actor="dana", at=NOW)
    assert reopened.state is ReplyState.DRAFT
    assert entry.to_state is ReplyState.DRAFT


def test_dry_run_then_real_post() -> None:
    approved, _ = apply(make_reply(), ReplyAction.APPROVE, actor="dana", at=NOW)
    would, _ = apply(approved, ReplyAction.DRY_RUN_POST, actor="dana", at=NOW)
    assert would.state is ReplyState.WOULD_POST
    assert next_state(would.state, ReplyAction.POST) is ReplyState.POSTED


def test_post_without_approver_is_refused() -> None:
    forged = make_reply(ReplyState.APPROVED)
    with pytest.raises(InvalidTransitionError, match="approver"):
        apply(forged, ReplyAction.POST, actor="mallory", at=NOW)


def test_store_limits() -> None:
    assert validate_reply_body(Store.APP_STORE, "x" * 5970)
    with pytest.raises(ReplyInvalidError) as caught:
        validate_reply_body(Store.GOOGLE_PLAY, "x" * 351)
    assert caught.value.details == {"length": 351, "limit": 350}
    with pytest.raises(ReplyInvalidError):
        validate_reply_body(Store.GOOGLE_PLAY, "   ")


def test_allowed_actions() -> None:
    assert set(allowed_actions(ReplyState.DRAFT)) == {
        ReplyAction.APPROVE,
        ReplyAction.EDIT,
        ReplyAction.REJECT,
    }
    assert allowed_actions(ReplyState.POSTED) == []
