import pytest
from pydantic import ValidationError

from review_radar.domain.models import Category, Triage


def test_category_labels_cover_every_member() -> None:
    assert {c.label for c in Category} >= {"Login / auth", "Payments / billing"}


def test_triage_normalizes_and_validates() -> None:
    triage = Triage.model_validate(
        {
            "sentiment": "negative",
            "category": "crash",
            "severity": "high",
            "summary": "  App crashes when signing in  ",
            "language": "de",
        }
    )
    assert triage.summary == "App crashes when signing in"
    with pytest.raises(ValidationError):
        Triage.model_validate({**triage.model_dump(), "language": "german"})
