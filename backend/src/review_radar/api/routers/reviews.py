from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from review_radar.api.deps import ReadModelDep
from review_radar.api.errors import ERROR_RESPONSES
from review_radar.application.views import Page, ReviewFilters, ReviewView
from review_radar.domain.errors import NotFoundError

router = APIRouter(prefix="/reviews", tags=["reviews"], responses=ERROR_RESPONSES)


@router.get("")
async def list_reviews(
    read: ReadModelDep, filters: Annotated[ReviewFilters, Query()]
) -> Page[ReviewView]:
    return await read.reviews(filters)


@router.get("/{review_id}")
async def get_review(read: ReadModelDep, review_id: UUID) -> ReviewView:
    review = await read.review(review_id)
    if review is None:
        raise NotFoundError("review not found", details={"review_id": str(review_id)})
    return review


@router.get("/{review_id}/similar")
async def similar_reviews(
    read: ReadModelDep, review_id: UUID, limit: Annotated[int, Query(ge=1, le=20)] = 5
) -> list[ReviewView]:
    """Nearest neighbours by summary embedding (pgvector cosine distance)."""
    return await read.similar_reviews(review_id, limit=limit)
