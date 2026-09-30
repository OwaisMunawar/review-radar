from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=5)


def make_sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: rows are mapped to frozen domain objects right after
    # a commit, and reloading each attribute would be a wasted round trip.
    return async_sessionmaker(engine, expire_on_commit=False)
