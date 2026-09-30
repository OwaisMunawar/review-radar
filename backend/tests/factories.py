from datetime import UTC, datetime, timedelta
from itertools import count

from review_radar.domain.models import (
    Category,
    IncomingReview,
    Sentiment,
    Severity,
    Store,
    Triage,
)

_ids = count(1)
BASE_TIME = datetime(2026, 6, 1, 12, tzinfo=UTC)


def incoming(
    *,
    store: Store = Store.GOOGLE_PLAY,
    rating: int = 2,
    body: str = "The app crashes when I log in.",
    version: str | None = "2.3.0",
    days: int = 0,
    external_id: str | None = None,
    language: str = "en",
) -> IncomingReview:
    return IncomingReview(
        store=store,
        external_id=external_id or f"r-{next(_ids)}",
        rating=rating,
        body=body,
        created_at=BASE_TIME + timedelta(days=days),
        title=None,
        language=language,
        app_version=version,
        territory="US",
        author="Test Reviewer",
    )


def triage(
    category: Category = Category.CRASH,
    sentiment: Sentiment = Sentiment.NEGATIVE,
    severity: Severity = Severity.HIGH,
    summary: str = "App crashes when signing in",
) -> Triage:
    return Triage(
        sentiment=sentiment,
        category=category,
        severity=severity,
        summary=summary,
        language="en",
        app_version="2.3.0",
    )
