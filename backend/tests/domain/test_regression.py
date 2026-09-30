import math
from dataclasses import replace

from review_radar.domain.regression import (
    RegressionPolicy,
    ReleaseSample,
    Segment,
    SegmentKind,
    compare_releases,
)

LOGIN = Segment(SegmentKind.CATEGORY, "login", "Login / auth")
UX = Segment(SegmentKind.CATEGORY, "ux", "UX")
PRAISE = Segment(SegmentKind.CATEGORY, "praise", "Praise")


def test_flags_a_real_spike_and_ignores_noise() -> None:
    baseline = ReleaseSample("2.2.0", 90, {"login": 3, "ux": 10, "praise": 40})
    candidate = ReleaseSample("2.3.0", 90, {"login": 24, "ux": 12, "praise": 25})

    results = compare_releases(baseline, candidate, [UX, PRAISE, LOGIN])

    top = results[0]
    assert top.segment == LOGIN
    assert top.flagged
    assert top.rate_ratio == 8.0
    assert top.headline == "Login / auth up 8.0x in 2.3.0"
    assert not any(r.flagged for r in results[1:])


def test_requires_minimum_count_even_when_significant() -> None:
    baseline = ReleaseSample("1.0.0", 1000, {"login": 0})
    candidate = ReleaseSample("1.1.0", 1000, {"login": 4})
    policy = RegressionPolicy(alpha=0.5, min_ratio=1.0, min_candidate_count=5)
    [result] = compare_releases(baseline, candidate, [LOGIN], policy)
    assert not result.flagged


def test_requires_minimum_ratio() -> None:
    baseline = ReleaseSample("1.0.0", 5000, {"ux": 1000})
    candidate = ReleaseSample("1.1.0", 5000, {"ux": 1300})
    [result] = compare_releases(baseline, candidate, [UX])
    assert result.adjusted_p_value < 0.01
    assert not result.flagged


def test_empty_inputs_yield_nothing() -> None:
    assert compare_releases(ReleaseSample("1", 0, {}), ReleaseSample("2", 10, {}), [UX]) == []
    assert compare_releases(ReleaseSample("1", 5, {}), ReleaseSample("2", 10, {}), []) == []


def test_headline_for_nan_ratio() -> None:
    [result] = compare_releases(
        ReleaseSample("1.0.0", 10, {"ux": 1}), ReleaseSample("1.1.0", 10, {"ux": 1}), [UX]
    )
    assert result.headline == "UX up 1.0x in 1.1.0"
    assert replace(result, rate_ratio=math.nan).headline == "UX up new in 1.1.0"
