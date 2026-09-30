"""Release comparison: version N against N-1 for every problem segment."""

import math

from review_radar.application.ports import ReadModel, ThemeLabel
from review_radar.application.views import (
    ReleaseComparisonView,
    SegmentComparisonView,
)
from review_radar.domain.errors import NotFoundError
from review_radar.domain.models import Category
from review_radar.domain.regression import (
    RegressionPolicy,
    ReleaseSample,
    Segment,
    SegmentComparison,
    SegmentKind,
    compare_releases,
)
from review_radar.domain.versions import previous_version, sort_versions

# More praise or more feature requests after a release is not a regression.
PROBLEM_CATEGORIES = tuple(
    c for c in Category if c not in (Category.PRAISE, Category.FEATURE_REQUEST)
)


def _view(c: SegmentComparison) -> SegmentComparisonView:
    return SegmentComparisonView(
        kind=c.segment.kind,
        key=c.segment.key,
        label=c.segment.label,
        baseline_count=c.baseline_count,
        candidate_count=c.candidate_count,
        baseline_rate=c.baseline_rate,
        candidate_rate=c.candidate_rate,
        rate_ratio=None if math.isnan(c.rate_ratio) else c.rate_ratio,
        z=c.z,
        p_value=c.p_value,
        adjusted_p_value=c.adjusted_p_value,
        flagged=c.flagged,
        headline=c.headline,
    )


class CompareReleases:
    def __init__(self, read: ReadModel, policy: RegressionPolicy | None = None) -> None:
        self._read = read
        self._policy = policy or RegressionPolicy()

    async def __call__(
        self, candidate: str | None = None, baseline: str | None = None
    ) -> ReleaseComparisonView:
        samples, theme_labels = await self._read.release_samples()
        summaries = {s.version: s for s in await self._read.releases()}
        by_version = {s.version: s for s in samples}
        versions = sort_versions(by_version)
        if not versions:
            raise NotFoundError("no triaged releases yet")

        candidate = candidate or versions[-1]
        if candidate not in by_version:
            raise NotFoundError(
                f"no reviews for version {candidate}", details={"version": candidate}
            )
        baseline = baseline or previous_version(versions, candidate)
        if baseline is None or baseline not in by_version:
            raise NotFoundError(
                f"no earlier release to compare {candidate} against",
                details={"version": candidate},
            )

        segments = self._segments(by_version[baseline], by_version[candidate], theme_labels)
        comparisons = compare_releases(
            by_version[baseline], by_version[candidate], segments, self._policy
        )
        return ReleaseComparisonView(
            # Samples only count triaged reviews, summaries count all of them,
            # so every sampled version has a summary.
            baseline=summaries[baseline],
            candidate=summaries[candidate],
            alpha=self._policy.alpha,
            min_ratio=self._policy.min_ratio,
            min_count=self._policy.min_candidate_count,
            segments=[_view(c) for c in comparisons],
        )

    async def all_flags(self) -> list[SegmentComparisonView]:
        """Flagged regressions across every consecutive pair of releases."""
        samples, _ = await self._read.release_samples()
        versions = sort_versions(s.version for s in samples)
        flags: list[SegmentComparisonView] = []
        for candidate in versions[1:]:
            comparison = await self(candidate)
            flags.extend(s for s in comparison.segments if s.flagged)
        return flags

    @staticmethod
    def _segments(
        baseline: ReleaseSample, candidate: ReleaseSample, theme_labels: dict[str, ThemeLabel]
    ) -> list[Segment]:
        segments = [
            Segment(SegmentKind.CATEGORY, f"category:{c.value}", c.label)
            for c in PROBLEM_CATEGORIES
        ]
        present = set(baseline.counts) | set(candidate.counts)
        segments += [
            Segment(SegmentKind.THEME, key, label.title)
            for key, label in sorted(theme_labels.items(), key=lambda kv: kv[1].title)
            if key in present and label.category in PROBLEM_CATEGORIES
        ]
        return segments
