from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from review_radar import __version__
from review_radar.api.deps import ContainerDep, ReadModelDep
from review_radar.application.views import OverviewView, ThemeView

router = APIRouter(tags=["dashboard"])


class Health(BaseModel):
    status: str
    version: str
    database: bool
    model: str
    demo_mode: bool


@router.get("/health")
async def health(container: ContainerDep) -> Health:
    try:
        async with container.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database = True
    except (OSError, SQLAlchemyError):
        database = False
    return Health(
        status="ok" if database else "degraded",
        version=__version__,
        database=database,
        model=container.settings.resolved_model,
        demo_mode=container.settings.demo_mode,
    )


@router.get("/overview")
async def overview(
    read: ReadModelDep, weeks: Annotated[int, Query(ge=1, le=104)] = 38
) -> OverviewView:
    return await read.overview(weeks=weeks)


@router.get("/themes")
async def themes(read: ReadModelDep) -> list[ThemeView]:
    return await read.themes()
