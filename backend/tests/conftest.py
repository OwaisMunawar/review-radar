"""Shared fixtures.

Database tests run against real Postgres 16 with pgvector: CI provides a service
container through TEST_DATABASE_URL, and locally we start one with
testcontainers. Mocks would hide exactly the behaviour worth testing here
(upserts, check constraints, the audit trigger, vector search).
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from review_radar.adapters.db.repositories import SqlUnitOfWork
from review_radar.adapters.db.session import make_engine, make_sessions

BACKEND = Path(__file__).resolve().parents[1]
TABLES = "reply_audit, replies, theme_members, themes, llm_calls, triages, reviews"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    if url := os.environ.get("TEST_DATABASE_URL"):
        yield url
        return
    from testcontainers.community.postgres import PostgresContainer  # noqa: PLC0415

    with PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def migrated(database_url: str) -> str:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return database_url


@pytest.fixture(scope="session")
async def engine(migrated: str) -> AsyncIterator[AsyncEngine]:
    engine = make_engine(migrated)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    return make_sessions(engine)


@pytest.fixture
def uow_factory(sessions: async_sessionmaker[AsyncSession]) -> "UowFactory":
    return UowFactory(sessions)


class UowFactory:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    def __call__(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self.sessions)
