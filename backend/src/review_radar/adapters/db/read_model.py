"""SQL implementation of the dashboard's query side."""

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from review_radar.adapters.db.tables import (
    LlmCallRow,
    ReplyAuditRow,
    ReplyRow,
    ReviewRow,
    ThemeMemberRow,
    ThemeRow,
    TriageRow,
)
from review_radar.application.ports import ThemeLabel
from review_radar.application.views import (
    AuditView,
    CategoryCount,
    OverviewView,
    Page,
    ReleaseSummaryView,
    ReplyView,
    ReviewFilters,
    ReviewView,
    ThemeView,
    TriageView,
    UsageTotals,
    WeekPoint,
)
from review_radar.domain.models import Category, Store
from review_radar.domain.regression import ReleaseSample
from review_radar.domain.replies import (
    REPLY_LIMITS,
    ReplyAction,
    ReplyState,
    allowed_actions,
)
from review_radar.domain.trend import Trend
from review_radar.domain.versions import version_key

# Outer joins make the last four columns nullable at runtime.
ReviewSelect = Select[ReviewRow, TriageRow, UUID, str, str]

_NEGATIVE: ColumnElement[float] = func.avg(
    case((TriageRow.sentiment == "negative", 1.0), else_=0.0)
)


def _as_float(value: object) -> float | None:
    return None if value is None else float(value)  # type: ignore[arg-type]


def _review_view(
    review: ReviewRow,
    triage: TriageRow | None,
    *,
    theme_id: UUID | None = None,
    theme_title: str | None = None,
    reply_state: str | None = None,
) -> ReviewView:
    return ReviewView(
        id=review.id,
        store=Store(review.store),
        external_id=review.external_id,
        rating=review.rating,
        title=review.title,
        body=review.body,
        language=review.language,
        app_version=review.app_version,
        territory=review.territory,
        author=review.author,
        created_at=review.created_at,
        triage=TriageView.model_validate(triage) if triage is not None else None,
        theme_id=theme_id,
        theme_title=theme_title,
        reply_state=ReplyState(reply_state) if reply_state else None,
    )


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SqlReadModel:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, model: str, demo_mode: bool
    ) -> None:
        self._sessions = sessions
        self._model = model
        self._demo_mode = demo_mode

    def _review_select(self) -> ReviewSelect:
        return (
            select(ReviewRow, TriageRow, ThemeRow.id, ThemeRow.title, ReplyRow.state)
            .outerjoin(TriageRow, TriageRow.review_id == ReviewRow.id)
            .outerjoin(ThemeMemberRow, ThemeMemberRow.review_id == ReviewRow.id)
            .outerjoin(ThemeRow, ThemeRow.id == ThemeMemberRow.theme_id)
            .outerjoin(ReplyRow, ReplyRow.review_id == ReviewRow.id)
        )

    async def _load_reviews(self, session: AsyncSession, stmt: ReviewSelect) -> list[ReviewView]:
        rows = (await session.execute(stmt)).all()
        return [
            _review_view(r, t, theme_id=tid, theme_title=title, reply_state=state)
            for r, t, tid, title, state in rows
        ]

    async def overview(self, *, weeks: int) -> OverviewView:
        async with self._sessions() as session:
            totals = (
                await session.execute(
                    select(
                        func.count(ReviewRow.id), func.avg(ReviewRow.rating), _NEGATIVE
                    ).outerjoin(TriageRow, TriageRow.review_id == ReviewRow.id)
                )
            ).one()
            week = func.date_trunc("week", ReviewRow.created_at).label("week")
            weekly_rows = (
                await session.execute(
                    select(week, func.count(ReviewRow.id), func.avg(ReviewRow.rating), _NEGATIVE)
                    .outerjoin(TriageRow, TriageRow.review_id == ReviewRow.id)
                    .group_by(week)
                    .order_by(week.desc())
                    .limit(weeks)
                )
            ).all()
            category_rows = (
                await session.execute(
                    select(TriageRow.category, func.count())
                    .group_by(TriageRow.category)
                    .order_by(func.count().desc(), TriageRow.category)
                )
            ).all()
            store_rows = (
                await session.execute(
                    select(ReviewRow.store, func.count()).group_by(ReviewRow.store)
                )
            ).all()
            pending = await session.scalar(
                select(func.count()).select_from(ReplyRow).where(ReplyRow.state == "draft")
            )
            usage = (
                await session.execute(
                    select(
                        func.count(LlmCallRow.id),
                        func.coalesce(func.sum(LlmCallRow.input_tokens), 0),
                        func.coalesce(func.sum(LlmCallRow.output_tokens), 0),
                        func.coalesce(func.sum(LlmCallRow.cost_usd), 0),
                    )
                )
            ).one()

        return OverviewView(
            total_reviews=totals[0],
            avg_rating=_as_float(totals[1]),
            negative_share=_as_float(totals[2]) if totals[0] else None,
            pending_replies=pending or 0,
            weekly=[
                WeekPoint(
                    week_start=wk.date(),
                    reviews=count,
                    avg_rating=_as_float(avg),
                    negative_share=_as_float(neg),
                )
                for wk, count, avg, neg in reversed(weekly_rows)
            ],
            categories=[CategoryCount(category=Category(c), count=n) for c, n in category_rows],
            stores={Store(s): n for s, n in store_rows},
            usage=UsageTotals(
                calls=usage[0],
                input_tokens=int(usage[1]),
                output_tokens=int(usage[2]),
                cost_usd=Decimal(usage[3]),
            ),
            model=self._model,
            demo_mode=self._demo_mode,
        )

    async def reviews(self, filters: ReviewFilters) -> Page[ReviewView]:
        conditions: list[ColumnElement[bool]] = []
        if filters.store:
            conditions.append(ReviewRow.store == filters.store.value)
        if filters.category:
            conditions.append(TriageRow.category == filters.category.value)
        if filters.sentiment:
            conditions.append(TriageRow.sentiment == filters.sentiment.value)
        if filters.severity:
            conditions.append(TriageRow.severity == filters.severity.value)
        if filters.version:
            conditions.append(ReviewRow.app_version == filters.version)
        if filters.rating:
            conditions.append(ReviewRow.rating == filters.rating)
        if filters.theme_id:
            conditions.append(ThemeMemberRow.theme_id == filters.theme_id)
        if filters.q:
            pattern = f"%{_escape_like(filters.q)}%"
            conditions.append(
                or_(
                    ReviewRow.body.ilike(pattern, escape="\\"),
                    ReviewRow.title.ilike(pattern, escape="\\"),
                    TriageRow.summary.ilike(pattern, escape="\\"),
                )
            )

        base = self._review_select().where(*conditions)
        async with self._sessions() as session:
            total = await session.scalar(select(func.count()).select_from(base.subquery()))
            items = await self._load_reviews(
                session,
                base.order_by(ReviewRow.created_at.desc(), ReviewRow.id)
                .limit(filters.limit)
                .offset(filters.offset),
            )
        return Page(items=items, total=total or 0, limit=filters.limit, offset=filters.offset)

    async def review(self, review_id: UUID) -> ReviewView | None:
        async with self._sessions() as session:
            items = await self._load_reviews(
                session, self._review_select().where(ReviewRow.id == review_id)
            )
        return items[0] if items else None

    async def similar_reviews(self, review_id: UUID, *, limit: int) -> list[ReviewView]:
        async with self._sessions() as session:
            vector = await session.scalar(
                select(TriageRow.embedding).where(TriageRow.review_id == review_id)
            )
            if vector is None:
                return []
            return await self._load_reviews(
                session,
                self._review_select()
                .where(ReviewRow.id != review_id, TriageRow.embedding.is_not(None))
                .order_by(TriageRow.embedding.cosine_distance(vector))
                .limit(limit),
            )

    async def themes(self) -> list[ThemeView]:
        async with self._sessions() as session:
            themes = (
                await session.scalars(
                    select(ThemeRow).order_by(ThemeRow.size.desc(), ThemeRow.title)
                )
            ).all()
            negative = dict(
                (
                    await session.execute(
                        select(ThemeMemberRow.theme_id, _NEGATIVE)
                        .join(TriageRow, TriageRow.review_id == ThemeMemberRow.review_id)
                        .group_by(ThemeMemberRow.theme_id)
                    )
                ).all()
            )
            reps = await self._load_reviews(
                session,
                self._review_select()
                .where(ThemeMemberRow.is_representative.is_(True))
                .order_by(ReviewRow.created_at.desc()),
            )
        by_theme: dict[UUID, list[ReviewView]] = defaultdict(list)
        for rep in reps:
            if rep.theme_id is not None:
                by_theme[rep.theme_id].append(rep)
        return [
            ThemeView(
                id=t.id,
                title=t.title,
                size=t.size,
                dominant_category=Category(t.dominant_category),
                trend=Trend(t.trend),
                weekly_counts=list(t.weekly_counts),
                negative_share=float(negative.get(t.id) or 0.0),
                representatives=by_theme[t.id],
            )
            for t in themes
        ]

    async def releases(self) -> list[ReleaseSummaryView]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(
                        ReviewRow.app_version,
                        func.count(ReviewRow.id),
                        func.avg(ReviewRow.rating),
                        _NEGATIVE,
                        func.min(ReviewRow.created_at),
                    )
                    .outerjoin(TriageRow, TriageRow.review_id == ReviewRow.id)
                    .where(ReviewRow.app_version.is_not(None))
                    .group_by(ReviewRow.app_version)
                )
            ).all()
        views = [
            ReleaseSummaryView(
                version=version,
                reviews=count,
                avg_rating=_as_float(avg),
                negative_share=_as_float(neg),
                first_review_at=first,
            )
            for version, count, avg, neg, first in rows
        ]
        return sorted(views, key=lambda v: version_key(v.version))

    async def release_samples(self) -> tuple[list[ReleaseSample], dict[str, ThemeLabel]]:
        async with self._sessions() as session:
            totals = (
                await session.execute(
                    select(ReviewRow.app_version, func.count())
                    .join(TriageRow, TriageRow.review_id == ReviewRow.id)
                    .where(ReviewRow.app_version.is_not(None))
                    .group_by(ReviewRow.app_version)
                )
            ).all()
            categories = (
                await session.execute(
                    select(ReviewRow.app_version, TriageRow.category, func.count())
                    .join(TriageRow, TriageRow.review_id == ReviewRow.id)
                    .where(ReviewRow.app_version.is_not(None))
                    .group_by(ReviewRow.app_version, TriageRow.category)
                )
            ).all()
            themes = (
                await session.execute(
                    select(ReviewRow.app_version, ThemeMemberRow.theme_id, func.count())
                    .join(ThemeMemberRow, ThemeMemberRow.review_id == ReviewRow.id)
                    .where(ReviewRow.app_version.is_not(None))
                    .group_by(ReviewRow.app_version, ThemeMemberRow.theme_id)
                )
            ).all()
            titles = (
                await session.execute(
                    select(ThemeRow.id, ThemeRow.title, ThemeRow.dominant_category)
                )
            ).all()

        counts: dict[str, dict[str, int]] = defaultdict(dict)
        for version, category, n in categories:
            counts[str(version)][f"category:{category}"] = n
        for version, theme_id, n in themes:
            counts[str(version)][f"theme:{theme_id}"] = n
        samples = [
            ReleaseSample(version=str(v), total=n, counts=counts[str(v)])
            for v, n in sorted(totals, key=lambda row: version_key(str(row[0])))
        ]
        return samples, {
            f"theme:{tid}": ThemeLabel(title=title, category=Category(category))
            for tid, title, category in titles
        }

    async def _replies(
        self,
        session: AsyncSession,
        conditions: Sequence[ColumnElement[bool]],
        limit: int,
        offset: int,
    ) -> tuple[list[ReplyView], int]:
        base = (
            select(ReplyRow, ReviewRow, TriageRow)
            .join(ReviewRow, ReviewRow.id == ReplyRow.review_id)
            .outerjoin(TriageRow, TriageRow.review_id == ReviewRow.id)
            .where(*conditions)
        )
        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        # Most severe first, so the queue surfaces what needs a human soonest.
        severity_rank = case(
            {"critical": 0, "high": 1, "medium": 2, "low": 3}, value=TriageRow.severity, else_=4
        )
        rows = (
            await session.execute(
                base.order_by(severity_rank, ReviewRow.created_at.desc(), ReplyRow.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        ids = [reply.id for reply, _, _ in rows]
        audit: dict[UUID, list[AuditView]] = defaultdict(list)
        if ids:
            for entry in (
                await session.scalars(
                    select(ReplyAuditRow)
                    .where(ReplyAuditRow.reply_id.in_(ids))
                    .order_by(ReplyAuditRow.at, ReplyAuditRow.id)
                )
            ).all():
                audit[entry.reply_id].append(
                    AuditView(
                        action=ReplyAction(entry.action),
                        from_state=ReplyState(entry.from_state) if entry.from_state else None,
                        to_state=ReplyState(entry.to_state),
                        actor=entry.actor,
                        note=entry.note,
                        at=entry.at,
                    )
                )
        views = [
            ReplyView(
                id=reply.id,
                state=ReplyState(reply.state),
                body=reply.body,
                drafted_body=reply.drafted_body,
                char_limit=REPLY_LIMITS[Store(reply.store)],
                model_name=reply.model_name,
                approved_by=reply.approved_by,
                approved_at=reply.approved_at,
                posted_at=reply.posted_at,
                updated_at=reply.updated_at,
                allowed_actions=allowed_actions(ReplyState(reply.state)),
                review=_review_view(review, triage, reply_state=reply.state),
                audit=audit[reply.id],
            )
            for reply, review, triage in rows
        ]
        return views, total

    async def replies(
        self, *, state: ReplyState | None, store: Store | None, limit: int, offset: int
    ) -> Page[ReplyView]:
        conditions: list[ColumnElement[bool]] = []
        if state:
            conditions.append(ReplyRow.state == state.value)
        if store:
            conditions.append(ReplyRow.store == store.value)
        async with self._sessions() as session:
            items, total = await self._replies(session, conditions, limit, offset)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def reply(self, reply_id: UUID) -> ReplyView | None:
        async with self._sessions() as session:
            items, _ = await self._replies(session, [ReplyRow.id == reply_id], 1, 0)
        return items[0] if items else None
