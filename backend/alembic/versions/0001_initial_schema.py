"""Initial schema: reviews, triage with pgvector embeddings, themes, replies and audit.

Revision ID: 0001
Revises:
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIMENSIONS = 256
TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("language", sa.String(8)),
        sa.Column("app_version", sa.String(32)),
        sa.Column("territory", sa.String(8)),
        sa.Column("author", sa.String(200)),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("ingested_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("store", "external_id", name="uq_reviews_store_external_id"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        sa.CheckConstraint("store IN ('app_store', 'google_play')", name="ck_reviews_store"),
    )
    op.create_index("ix_reviews_app_version", "reviews", ["app_version"])
    op.create_index("ix_reviews_created_at", "reviews", ["created_at"])

    op.create_table(
        "triages",
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sentiment", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("app_version", sa.String(32)),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("embedding", Vector(DIMENSIONS)),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_triages_category", "triages", ["category"])
    # HNSW over cosine distance backs "similar reviews" lookups.
    op.execute(
        "CREATE INDEX ix_triages_embedding ON triages USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="SET NULL"),
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_llm_calls_purpose", "llm_calls", ["purpose"])

    op.create_table(
        "themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("dominant_category", sa.String(32), nullable=False),
        sa.Column("trend", sa.String(16), nullable=False),
        sa.Column("weekly_counts", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("centroid", Vector(DIMENSIONS), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "theme_members",
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("themes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("is_representative", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_theme_members_review_id", "theme_members", ["review_id"])

    op.create_table(
        "replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("store", sa.String(20), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("drafted_body", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("approved_by", sa.String(64)),
        sa.Column("approved_at", TIMESTAMP),
        sa.Column("posted_at", TIMESTAMP),
        sa.Column("external_reply_id", sa.String(200)),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("updated_at", TIMESTAMP, nullable=False),
        # The domain refuses to post unapproved replies; this makes it impossible
        # at the storage layer too, whatever code path writes the row.
        sa.CheckConstraint(
            "state NOT IN ('posted', 'would_post') OR approved_by IS NOT NULL",
            name="ck_replies_posted_requires_approval",
        ),
        sa.CheckConstraint(
            "state IN ('draft', 'approved', 'edited', 'rejected', 'posted', 'would_post')",
            name="ck_replies_state",
        ),
    )
    op.create_index("ix_replies_state", "replies", ["state"])

    op.create_table(
        "reply_audit",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "reply_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("replies.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("from_state", sa.String(16)),
        sa.Column("to_state", sa.String(16), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("at", TIMESTAMP, nullable=False),
    )
    op.create_index("ix_reply_audit_reply_id", "reply_audit", ["reply_id"])
    op.execute(
        """
        CREATE FUNCTION reply_audit_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'reply_audit is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER reply_audit_no_update_delete
        BEFORE UPDATE OR DELETE ON reply_audit
        FOR EACH ROW EXECUTE FUNCTION reply_audit_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS reply_audit_no_update_delete ON reply_audit")
    op.execute("DROP FUNCTION IF EXISTS reply_audit_append_only()")
    for table in ("reply_audit", "replies", "theme_members", "themes", "llm_calls", "triages"):
        op.drop_table(table)
    op.drop_table("reviews")
