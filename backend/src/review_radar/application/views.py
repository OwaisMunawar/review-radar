"""Read models returned to the API.

These are the response bodies, defined once. The web client's TypeScript types
are generated from the OpenAPI schema these produce.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from review_radar.domain.models import Category, Sentiment, Severity, Store
from review_radar.domain.regression import SegmentKind
from review_radar.domain.replies import ReplyAction, ReplyState
from review_radar.domain.trend import Trend


class View(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)


class Page[T](View):
    items: list[T]
    total: int
    limit: int
    offset: int


class TriageView(View):
    sentiment: Sentiment
    category: Category
    severity: Severity
    summary: str
    language: str
    model_name: str


class ReviewView(View):
    id: UUID
    store: Store
    external_id: str
    rating: int
    title: str | None
    body: str
    language: str | None
    app_version: str | None
    territory: str | None
    author: str | None
    created_at: datetime
    triage: TriageView | None
    theme_id: UUID | None = None
    theme_title: str | None = None
    reply_state: ReplyState | None = None


class ReviewFilters(BaseModel):
    store: Store | None = None
    category: Category | None = None
    sentiment: Sentiment | None = None
    severity: Severity | None = None
    version: str | None = Field(default=None, max_length=32)
    rating: int | None = Field(default=None, ge=1, le=5)
    theme_id: UUID | None = None
    q: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class WeekPoint(View):
    week_start: date
    reviews: int
    avg_rating: float | None
    negative_share: float | None


class CategoryCount(View):
    category: Category
    count: int


class UsageTotals(View):
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class OverviewView(View):
    total_reviews: int
    avg_rating: float | None
    negative_share: float | None
    pending_replies: int
    weekly: list[WeekPoint]
    categories: list[CategoryCount]
    stores: dict[Store, int]
    usage: UsageTotals
    model: str
    demo_mode: bool


class ThemeView(View):
    id: UUID
    title: str
    size: int
    dominant_category: Category
    trend: Trend
    weekly_counts: list[int]
    negative_share: float
    representatives: list[ReviewView]


class ReleaseSummaryView(View):
    version: str
    reviews: int
    avg_rating: float | None
    negative_share: float | None
    first_review_at: datetime


class SegmentComparisonView(View):
    baseline_version: str
    candidate_version: str
    kind: SegmentKind
    key: str
    label: str
    baseline_count: int
    candidate_count: int
    baseline_rate: float
    candidate_rate: float
    rate_ratio: float | None
    z: float
    p_value: float
    adjusted_p_value: float
    flagged: bool
    headline: str


class ReleaseComparisonView(View):
    baseline: ReleaseSummaryView
    candidate: ReleaseSummaryView
    alpha: float
    min_ratio: float
    min_count: int
    segments: list[SegmentComparisonView]


class AuditView(View):
    action: ReplyAction
    from_state: ReplyState | None
    to_state: ReplyState
    actor: str
    note: str | None
    at: datetime


class ReplyView(View):
    id: UUID
    state: ReplyState
    body: str
    drafted_body: str
    char_limit: int
    model_name: str
    approved_by: str | None
    approved_at: datetime | None
    posted_at: datetime | None
    updated_at: datetime
    allowed_actions: list[ReplyAction]
    review: ReviewView
    audit: list[AuditView]


class PipelineReport(View):
    ingested: int = 0
    updated: int = 0
    triaged: int = 0
    triage_failures: int = 0
    embedded: int = 0
    themes: int = 0
    drafted: int = 0
