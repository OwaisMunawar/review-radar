"""SQLAlchemy mapping. The Alembic migration is the source of truth for DDL;
these classes must stay in step with it (tests run against the migrated schema).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from review_radar.domain.models import EMBEDDING_DIMENSIONS


class Base(DeclarativeBase):
    pass


class ReviewRow(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("store", "external_id", name="uq_reviews_store_external_id"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(200))
    rating: Mapped[int] = mapped_column(SmallInteger)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(8))
    app_version: Mapped[str | None] = mapped_column(String(32), index=True)
    territory: Mapped[str | None] = mapped_column(String(8))
    author: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    triage: Mapped["TriageRow | None"] = relationship(back_populates="review", lazy="raise")


class TriageRow(Base):
    __tablename__ = "triages"

    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True
    )
    sentiment: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8))
    app_version: Mapped[str | None] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column(String(120))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    review: Mapped[ReviewRow] = relationship(back_populates="triage", lazy="raise")


class LlmCallRow(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    purpose: Mapped[str] = mapped_column(String(20), index=True)
    model_name: Mapped[str] = mapped_column(String(120))
    review_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reviews.id", ondelete="SET NULL")
    )
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ThemeRow(Base):
    __tablename__ = "themes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column(Integer)
    dominant_category: Mapped[str] = mapped_column(String(32))
    trend: Mapped[str] = mapped_column(String(16))
    weekly_counts: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    centroid: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ThemeMemberRow(Base):
    __tablename__ = "theme_members"

    theme_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("themes.id", ondelete="CASCADE"), primary_key=True
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    is_representative: Mapped[bool] = mapped_column(Boolean, default=False)


class ReplyRow(Base):
    __tablename__ = "replies"
    __table_args__ = (
        CheckConstraint(
            "state NOT IN ('posted', 'would_post') OR approved_by IS NOT NULL",
            name="ck_replies_posted_requires_approval",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), unique=True
    )
    store: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(16), index=True)
    body: Mapped[str] = mapped_column(Text)
    drafted_body: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(120))
    approved_by: Mapped[str | None] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_reply_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReplyAuditRow(Base):
    __tablename__ = "reply_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reply_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("replies.id"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str] = mapped_column(String(16))
    actor: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
