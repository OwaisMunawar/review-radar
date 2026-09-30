"""Release-over-release regression detection.

A segment (a category or a theme) is flagged when its share of reviews in the
candidate release is significantly higher than in the release before it, the
increase is large enough to matter, and there are enough reviews to act on.
All three gates are needed: significance alone fires on tiny effects in large
samples, and ratio alone fires on 1 -> 3 reviews.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from review_radar.domain.stats import holm_adjust, two_proportion_z_test


class SegmentKind(StrEnum):
    CATEGORY = "category"
    THEME = "theme"


@dataclass(frozen=True, slots=True)
class Segment:
    kind: SegmentKind
    key: str
    label: str


@dataclass(frozen=True, slots=True)
class ReleaseSample:
    version: str
    total: int
    counts: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class RegressionPolicy:
    alpha: float = 0.01
    min_ratio: float = 2.0
    min_candidate_count: int = 5


@dataclass(frozen=True, slots=True)
class SegmentComparison:
    segment: Segment
    baseline_version: str
    candidate_version: str
    baseline_count: int
    baseline_total: int
    candidate_count: int
    candidate_total: int
    baseline_rate: float
    candidate_rate: float
    rate_ratio: float
    z: float
    p_value: float
    adjusted_p_value: float
    flagged: bool

    @property
    def headline(self) -> str:
        ratio = "new" if math.isnan(self.rate_ratio) else f"{self.rate_ratio:.1f}x"
        return f"{self.segment.label} up {ratio} in {self.candidate_version}"


def compare_releases(
    baseline: ReleaseSample,
    candidate: ReleaseSample,
    segments: Sequence[Segment],
    policy: RegressionPolicy | None = None,
) -> list[SegmentComparison]:
    """Compare every segment between two releases, most suspicious first."""
    policy = policy or RegressionPolicy()
    if baseline.total == 0 or candidate.total == 0 or not segments:
        return []

    tests = [
        two_proportion_z_test(
            baseline.counts.get(s.key, 0),
            baseline.total,
            candidate.counts.get(s.key, 0),
            candidate.total,
        )
        for s in segments
    ]
    adjusted = holm_adjust([t.p_value for t in tests])

    results: list[SegmentComparison] = []
    for segment, test, adj in zip(segments, tests, adjusted, strict=True):
        candidate_count = candidate.counts.get(segment.key, 0)
        flagged = (
            adj < policy.alpha
            and test.rate_ratio >= policy.min_ratio
            and candidate_count >= policy.min_candidate_count
        )
        results.append(
            SegmentComparison(
                segment=segment,
                baseline_version=baseline.version,
                candidate_version=candidate.version,
                baseline_count=baseline.counts.get(segment.key, 0),
                baseline_total=baseline.total,
                candidate_count=candidate_count,
                candidate_total=candidate.total,
                baseline_rate=test.baseline_rate,
                candidate_rate=test.candidate_rate,
                rate_ratio=test.rate_ratio,
                z=test.z,
                p_value=test.p_value,
                adjusted_p_value=adj,
                flagged=flagged,
            )
        )
    results.sort(key=lambda c: (not c.flagged, c.adjusted_p_value, -c.candidate_count))
    return results
