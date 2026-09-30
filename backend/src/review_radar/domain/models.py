"""Core vocabulary shared by every layer. Nothing here performs IO."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Store(StrEnum):
    APP_STORE = "app_store"
    GOOGLE_PLAY = "google_play"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Category(StrEnum):
    CRASH = "crash"
    PERFORMANCE = "performance"
    LOGIN = "login"
    PAYMENTS = "payments"
    UX = "ux"
    FEATURE_REQUEST = "feature_request"
    PRAISE = "praise"
    OTHER = "other"

    @property
    def label(self) -> str:
        return _CATEGORY_LABELS[self]


_CATEGORY_LABELS: dict[Category, str] = {
    Category.CRASH: "Crash",
    Category.PERFORMANCE: "Performance",
    Category.LOGIN: "Login / auth",
    Category.PAYMENTS: "Payments / billing",
    Category.UX: "UX",
    Category.FEATURE_REQUEST: "Feature request",
    Category.PRAISE: "Praise",
    Category.OTHER: "Other",
}


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LlmPurpose(StrEnum):
    TRIAGE = "triage"
    REPLY = "reply"
    THEME_TITLE = "theme_title"
    EMBEDDING = "embedding"


@dataclass(frozen=True, slots=True)
class IncomingReview:
    """A review as a store reports it, before any enrichment.

    `external_id` is the store's own identifier; together with `store` it is the
    natural key that makes ingestion idempotent.
    """

    store: Store
    external_id: str
    rating: int
    body: str
    created_at: datetime
    title: str | None = None
    language: str | None = None
    app_version: str | None = None
    territory: str | None = None
    author: str | None = None


ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=140)]


class Triage(BaseModel):
    """Structured output of the triage agent.

    Field descriptions double as instructions: PydanticAI sends them to the model
    as part of the output tool schema.
    """

    model_config = ConfigDict(frozen=True)

    sentiment: Sentiment = Field(description="Overall tone of the review.")
    category: Category = Field(
        description=(
            "The single best bucket. Prefer 'crash' when the app closes or freezes, even if it "
            "happens during login. Use 'login' for sign-in or session problems without a crash."
        )
    )
    severity: Severity = Field(
        description=(
            "critical: data loss, cannot use the app at all, or charged incorrectly. "
            "high: a core flow is broken. medium: annoying but has a workaround. "
            "low: cosmetic, suggestions and praise."
        )
    )
    app_version: str | None = Field(
        default=None,
        description="App version the review refers to, e.g. '2.3.0'. Null if not stated.",
    )
    summary: ShortText = Field(
        description=(
            "One short English sentence that normalizes the point of the review so similar "
            "reviews read alike, e.g. 'App crashes when signing in'. No names, no quotes."
        )
    )
    language: str = Field(
        default="en",
        pattern=r"^[a-z]{2}$",
        description="ISO 639-1 code of the language the review is written in.",
    )


class ReplyText(BaseModel):
    """Structured output of the reply agent."""

    body: str = Field(
        description="The reply exactly as it should appear under the review, in the reviewer's "
        "language."
    )


class ThemeTitle(BaseModel):
    """Structured output of the theme naming agent."""

    title: str = Field(
        min_length=3,
        max_length=60,
        description="A 2 to 6 word title that names the shared issue, e.g. 'Crash on sign-in'.",
    )


@dataclass(frozen=True, slots=True)
class LlmUsage:
    """Token and cost accounting for one model call, persisted per call."""

    purpose: LlmPurpose
    model_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    duration_ms: int
