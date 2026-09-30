"""SQLAlchemy implementations of the write-side ports."""

from collections.abc import Sequence
from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import Integer, delete, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from review_radar.adapters.db.tables import (
    LlmCallRow,
    ReplyAuditRow,
    ReplyRow,
    ReviewRow,
    ThemeMemberRow,
    ThemeRow,
    TriageRow,
)
from review_radar.application.ports import EmbeddedSummary, NewTheme, UpsertResult
from review_radar.domain.models import (
    Category,
    IncomingReview,
    LlmUsage,
    Sentiment,
    Severity,
    Store,
    StoredReview,
    Triage,
)
from review_radar.domain.replies import AuditEntry, Reply, ReplyState


def triage_from_row(row: TriageRow) -> Triage:
    return Triage(
        sentiment=Sentiment(row.sentiment),
        category=Category(row.category),
        severity=Severity(row.severity),
        app_version=row.app_version,
        summary=row.summary,
        language=row.language,
    )


def review_from_row(row: ReviewRow, triage: TriageRow | None = None) -> StoredReview:
    return StoredReview(
        id=row.id,
        store=Store(row.store),
        external_id=row.external_id,
        rating=row.rating,
        body=row.body,
        created_at=row.created_at,
        title=row.title,
        language=row.language,
        app_version=row.app_version,
        territory=row.territory,
        author=row.author,
        triage=triage_from_row(triage) if triage is not None else None,
    )


def reply_from_row(row: ReplyRow) -> Reply:
    return Reply(
        id=row.id,
        review_id=row.review_id,
        store=Store(row.store),
        state=ReplyState(row.state),
        body=row.body,
        drafted_body=row.drafted_body,
        model_name=row.model_name,
        created_at=row.created_at,
        updated_at=row.updated_at,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        posted_at=row.posted_at,
        external_reply_id=row.external_reply_id,
    )


class SqlReviewRepository:
    # asyncpg caps a statement at 32767 bind parameters; 11 columns per row.
    _CHUNK = 1000

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, reviews: Sequence[IncomingReview]) -> UpsertResult:
        inserted = updated = 0
        for start in range(0, len(reviews), self._CHUNK):
            chunk = reviews[start : start + self._CHUNK]
            values = [
                {
                    "store": r.store.value,
                    "external_id": r.external_id,
                    "rating": r.rating,
                    "title": r.title,
                    "body": r.body,
                    "language": r.language,
                    "app_version": r.app_version,
                    "territory": r.territory,
                    "author": r.author,
                    "created_at": r.created_at,
                }
                for r in chunk
            ]
            stmt = insert(ReviewRow).values(values)
            # Reviewers can edit a review; the newest text wins. `xmax = 0` is
            # Postgres' tell for "this row was inserted, not updated".
            upsert = stmt.on_conflict_do_update(
                constraint="uq_reviews_store_external_id",
                set_={
                    "rating": stmt.excluded.rating,
                    "title": stmt.excluded.title,
                    "body": stmt.excluded.body,
                    "app_version": func.coalesce(stmt.excluded.app_version, ReviewRow.app_version),
                    "updated_at": func.now(),
                },
                where=(ReviewRow.body != stmt.excluded.body)
                | (ReviewRow.rating != stmt.excluded.rating),
            ).returning(literal_column("xmax", Integer) == 0)
            flags = (await self._session.execute(upsert)).scalars().all()
            inserted += sum(1 for f in flags if f)
            updated += sum(1 for f in flags if not f)
        return UpsertResult(inserted=inserted, updated=updated)

    async def get(self, review_id: UUID) -> StoredReview | None:
        row = await self._session.get(
            ReviewRow, review_id, options=[selectinload(ReviewRow.triage)]
        )
        return review_from_row(row, row.triage) if row else None

    async def list_untriaged(self, limit: int) -> list[StoredReview]:
        stmt = (
            select(ReviewRow)
            .outerjoin(TriageRow, TriageRow.review_id == ReviewRow.id)
            .where(TriageRow.review_id.is_(None))
            .order_by(ReviewRow.created_at, ReviewRow.id)
            .limit(limit)
        )
        return [review_from_row(r) for r in (await self._session.scalars(stmt)).all()]

    async def list_without_reply(self, limit: int) -> list[StoredReview]:
        stmt = (
            select(ReviewRow, TriageRow)
            .join(TriageRow, TriageRow.review_id == ReviewRow.id)
            .outerjoin(ReplyRow, ReplyRow.review_id == ReviewRow.id)
            .where(ReplyRow.id.is_(None))
            .order_by(ReviewRow.created_at.desc(), ReviewRow.id)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [review_from_row(review, triage) for review, triage in rows]


class SqlTriageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, review_id: UUID, triage: Triage, model_name: str) -> None:
        values = {
            "sentiment": triage.sentiment.value,
            "category": triage.category.value,
            "severity": triage.severity.value,
            "summary": triage.summary,
            "language": triage.language,
            "app_version": triage.app_version,
            "model_name": model_name,
        }
        stmt = insert(TriageRow).values(review_id=review_id, **values)
        # Re-triage replaces the verdict and drops the stale embedding.
        stmt = stmt.on_conflict_do_update(
            index_elements=[TriageRow.review_id],
            set_={**values, "embedding": None, "created_at": func.now()},
        )
        await self._session.execute(stmt)

    async def list_missing_embeddings(self, limit: int) -> list[tuple[UUID, str]]:
        stmt = (
            select(TriageRow.review_id, TriageRow.summary)
            .where(TriageRow.embedding.is_(None))
            .order_by(TriageRow.review_id)
            .limit(limit)
        )
        return [(rid, summary) for rid, summary in (await self._session.execute(stmt))]

    async def set_embeddings(self, vectors: Sequence[tuple[UUID, list[float]]]) -> None:
        for review_id, vector in vectors:
            await self._session.execute(
                update(TriageRow).where(TriageRow.review_id == review_id).values(embedding=vector)
            )

    async def list_embedded(self) -> list[EmbeddedSummary]:
        stmt = (
            select(
                TriageRow.review_id,
                TriageRow.summary,
                TriageRow.category,
                ReviewRow.created_at,
                TriageRow.embedding,
            )
            .join(ReviewRow, ReviewRow.id == TriageRow.review_id)
            .where(TriageRow.embedding.is_not(None))
            .order_by(ReviewRow.created_at, TriageRow.review_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            EmbeddedSummary(
                review_id=rid,
                summary=summary,
                category=Category(category),
                created_at=created_at,
                vector=[float(v) for v in vector or ()],
            )
            for rid, summary, category, created_at, vector in rows
        ]


class SqlThemeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_all(self, themes: Sequence[NewTheme]) -> list[UUID]:
        # Themes are a derived view over triaged reviews, rebuilt as a whole so
        # that ids never point at a clustering that no longer exists.
        await self._session.execute(delete(ThemeRow))
        ids: list[UUID] = []
        for theme in themes:
            row = ThemeRow(
                title=theme.title,
                size=len(theme.member_ids),
                dominant_category=theme.dominant_category.value,
                trend=theme.trend.value,
                weekly_counts=theme.weekly_counts,
                centroid=theme.centroid,
            )
            self._session.add(row)
            await self._session.flush()
            representatives = set(theme.representative_ids)
            self._session.add_all(
                ThemeMemberRow(
                    theme_id=row.id, review_id=rid, is_representative=rid in representatives
                )
                for rid in theme.member_ids
            )
            ids.append(row.id)
        await self._session.flush()
        return ids


class SqlReplyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, reply: Reply) -> None:
        self._session.add(
            ReplyRow(
                id=reply.id,
                review_id=reply.review_id,
                store=reply.store.value,
                state=reply.state.value,
                body=reply.body,
                drafted_body=reply.drafted_body,
                model_name=reply.model_name,
                created_at=reply.created_at,
                updated_at=reply.updated_at,
            )
        )
        await self._session.flush()

    async def get(self, reply_id: UUID, *, for_update: bool = False) -> Reply | None:
        stmt = select(ReplyRow).where(ReplyRow.id == reply_id)
        if for_update:
            # Two reviewers approving and rejecting at once must serialize.
            stmt = stmt.with_for_update()
        row = (await self._session.scalars(stmt)).one_or_none()
        return reply_from_row(row) if row else None

    async def save(self, reply: Reply) -> None:
        await self._session.execute(
            update(ReplyRow)
            .where(ReplyRow.id == reply.id)
            .values(
                state=reply.state.value,
                body=reply.body,
                approved_by=reply.approved_by,
                approved_at=reply.approved_at,
                posted_at=reply.posted_at,
                external_reply_id=reply.external_reply_id,
                updated_at=reply.updated_at,
            )
        )

    async def append_audit(self, entry: AuditEntry) -> None:
        self._session.add(
            ReplyAuditRow(
                reply_id=entry.reply_id,
                action=entry.action.value,
                from_state=entry.from_state.value if entry.from_state else None,
                to_state=entry.to_state.value,
                actor=entry.actor,
                note=entry.note,
                at=entry.at,
            )
        )
        await self._session.flush()


class SqlUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, usage: LlmUsage, *, review_id: UUID | None = None) -> None:
        self._session.add(
            LlmCallRow(
                purpose=usage.purpose.value,
                model_name=usage.model_name,
                review_id=review_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=usage.cost_usd,
                duration_ms=usage.duration_ms,
            )
        )


class SqlUnitOfWork:
    reviews: SqlReviewRepository
    triages: SqlTriageRepository
    themes: SqlThemeRepository
    replies: SqlReplyRepository
    usage: SqlUsageRepository

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def __aenter__(self) -> Self:
        self._session = self._sessions()
        self.reviews = SqlReviewRepository(self._session)
        self.triages = SqlTriageRepository(self._session)
        self.themes = SqlThemeRepository(self._session)
        self.replies = SqlReplyRepository(self._session)
        self.usage = SqlUsageRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Anything not explicitly committed is rolled back, including on error.
        await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()
