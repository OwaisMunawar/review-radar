from typing import Annotated

from fastapi import APIRouter, Query

from review_radar.api.deps import CompareReleasesDep, ReadModelDep
from review_radar.api.errors import ERROR_RESPONSES
from review_radar.application.views import (
    ReleaseComparisonView,
    ReleaseSummaryView,
    SegmentComparisonView,
)

router = APIRouter(prefix="/releases", tags=["releases"], responses=ERROR_RESPONSES)

Version = Annotated[str | None, Query(max_length=32, pattern=r"^\d+(\.\d+){0,3}$")]


@router.get("")
async def list_releases(read: ReadModelDep) -> list[ReleaseSummaryView]:
    return await read.releases()


@router.get("/compare")
async def compare(
    releases: CompareReleasesDep, candidate: Version = None, baseline: Version = None
) -> ReleaseComparisonView:
    """Compare a release with the one before it (or with `baseline`)."""
    return await releases(candidate, baseline)


@router.get("/regressions")
async def regressions(releases: CompareReleasesDep) -> list[SegmentComparisonView]:
    """Every flagged segment across consecutive release pairs."""
    return await releases.all_flags()
