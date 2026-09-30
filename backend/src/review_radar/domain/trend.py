"""Weekly volume buckets and a coarse trend label for themes."""

from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import StrEnum


class Trend(StrEnum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"


def weekly_buckets(timestamps: Iterable[datetime], *, end: datetime, weeks: int) -> list[int]:
    """Counts per 7-day window, oldest first, with the last window ending at `end`.

    `end` is passed in rather than read from the clock so that the demo dataset,
    which ends on a fixed date, renders the same sparklines every day.
    """
    buckets = [0] * weeks
    start = end - timedelta(weeks=weeks)
    for ts in timestamps:
        if not (start < ts <= end):
            continue
        index = min(weeks - 1, int((ts - start) / timedelta(weeks=1)))
        buckets[index] += 1
    return buckets


def classify_trend(buckets: list[int], *, window: int = 4, min_volume: int = 3) -> Trend:
    """Compare the last `window` weeks with the `window` weeks before them."""
    recent = sum(buckets[-window:])
    prior = sum(buckets[-2 * window : -window])
    if recent >= min_volume and recent >= 1.5 * max(prior, 1):
        return Trend.RISING
    if prior >= min_volume and recent <= 0.5 * prior:
        return Trend.FALLING
    return Trend.STABLE
