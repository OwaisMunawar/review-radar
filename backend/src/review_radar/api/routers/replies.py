from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from review_radar.api.deps import PostReplyDep, ReadModelDep, ReviewReplyDep
from review_radar.api.errors import ERROR_RESPONSES
from review_radar.application.views import Page, ReplyView
from review_radar.domain.errors import NotFoundError
from review_radar.domain.models import Store
from review_radar.domain.replies import ReplyAction, ReplyState

router = APIRouter(prefix="/replies", tags=["replies"], responses=ERROR_RESPONSES)

# There is no auth in this project yet (see the roadmap); the actor is who the
# client says it is, validated so it is at least safe to store and display.
Actor = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[\w.@+ -]+$")]


class ActorBody(BaseModel):
    actor: Actor


class EditBody(ActorBody):
    body: str = Field(min_length=1, max_length=6000)


class RejectBody(ActorBody):
    note: str | None = Field(default=None, max_length=500)


async def _view(read: ReadModelDep, reply_id: UUID) -> ReplyView:
    view = await read.reply(reply_id)
    if view is None:
        raise NotFoundError("reply not found", details={"reply_id": str(reply_id)})
    return view


@router.get("")
async def list_replies(
    read: ReadModelDep,
    state: ReplyState | None = None,
    store: Store | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ReplyView]:
    return await read.replies(state=state, store=store, limit=limit, offset=offset)


@router.get("/{reply_id}")
async def get_reply(read: ReadModelDep, reply_id: UUID) -> ReplyView:
    return await _view(read, reply_id)


@router.post("/{reply_id}/approve")
async def approve(
    read: ReadModelDep, act: ReviewReplyDep, reply_id: UUID, payload: ActorBody
) -> ReplyView:
    await act(reply_id, ReplyAction.APPROVE, actor=payload.actor)
    return await _view(read, reply_id)


@router.post("/{reply_id}/edit")
async def edit(
    read: ReadModelDep, act: ReviewReplyDep, reply_id: UUID, payload: EditBody
) -> ReplyView:
    await act(reply_id, ReplyAction.EDIT, actor=payload.actor, body=payload.body)
    return await _view(read, reply_id)


@router.post("/{reply_id}/reject")
async def reject(
    read: ReadModelDep, act: ReviewReplyDep, reply_id: UUID, payload: RejectBody
) -> ReplyView:
    await act(reply_id, ReplyAction.REJECT, actor=payload.actor, note=payload.note)
    return await _view(read, reply_id)


@router.post("/{reply_id}/redraft")
async def redraft(
    read: ReadModelDep, act: ReviewReplyDep, reply_id: UUID, payload: ActorBody
) -> ReplyView:
    await act(reply_id, ReplyAction.REDRAFT, actor=payload.actor)
    return await _view(read, reply_id)


@router.post("/{reply_id}/post")
async def post(
    read: ReadModelDep, publish: PostReplyDep, reply_id: UUID, payload: ActorBody
) -> ReplyView:
    """Post an approved reply. Without store keys and POSTING_ENABLED this is a dry run."""
    await publish(reply_id, actor=payload.actor)
    return await _view(read, reply_id)
