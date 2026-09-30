from datetime import UTC, datetime, timedelta

from review_radar.domain.trend import Trend, classify_trend, weekly_buckets

END = datetime(2026, 9, 1, tzinfo=UTC)


def test_weekly_buckets_oldest_first_and_bounded() -> None:
    stamps = [END, END - timedelta(days=1), END - timedelta(days=8), END - timedelta(weeks=10)]
    assert weekly_buckets(stamps, end=END, weeks=3) == [0, 1, 2]


def test_classify_trend() -> None:
    assert classify_trend([0, 0, 0, 0, 1, 2, 3, 4]) is Trend.RISING
    assert classify_trend([5, 5, 5, 5, 1, 0, 1, 0]) is Trend.FALLING
    assert classify_trend([2, 2, 2, 2, 2, 2, 2, 2]) is Trend.STABLE
    assert classify_trend([0, 0, 0, 0, 0, 1, 0, 0]) is Trend.STABLE
