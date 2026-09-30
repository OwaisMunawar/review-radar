"""Small, dependency-free statistics used by regression detection.

See docs/ARCHITECTURE.md (ADR-003) for why a one-sided two-proportion z-test
with Holm correction was chosen over chi-square or Fisher's exact test.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProportionTest:
    baseline_rate: float
    candidate_rate: float
    rate_ratio: float
    z: float
    p_value: float


def normal_sf(z: float) -> float:
    """P(Z > z) for a standard normal, via erfc for precision in the far tail."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def rate_ratio(x_base: int, n_base: int, x_cand: int, n_cand: int) -> float:
    """Candidate rate divided by baseline rate.

    When either count is zero we add 0.5 to both counts (Haldane-Anscombe) so a
    category that went from 0 to 12 reports a finite, conservative ratio instead
    of infinity.
    """
    if n_base == 0 or n_cand == 0:
        return math.nan
    if x_base == 0 or x_cand == 0:
        return ((x_cand + 0.5) / (n_cand + 1.0)) / ((x_base + 0.5) / (n_base + 1.0))
    return (x_cand / n_cand) / (x_base / n_base)


def two_proportion_z_test(x_base: int, n_base: int, x_cand: int, n_cand: int) -> ProportionTest:
    """One-sided pooled z-test for H1: candidate rate > baseline rate."""
    if min(n_base, n_cand) <= 0:
        raise ValueError("both samples need at least one review")
    if not (0 <= x_base <= n_base and 0 <= x_cand <= n_cand):
        raise ValueError("counts must be between 0 and the sample size")

    p_base = x_base / n_base
    p_cand = x_cand / n_cand
    pooled = (x_base + x_cand) / (n_base + n_cand)
    variance = pooled * (1.0 - pooled) * (1.0 / n_base + 1.0 / n_cand)
    # Zero variance means both rates are 0 or both are 1: no evidence either way.
    z = 0.0 if variance == 0.0 else (p_cand - p_base) / math.sqrt(variance)
    return ProportionTest(
        baseline_rate=p_base,
        candidate_rate=p_cand,
        rate_ratio=rate_ratio(x_base, n_base, x_cand, n_cand),
        z=z,
        p_value=normal_sf(z),
    )


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values, returned in input order.

    Each release comparison tests every category and theme at once, so without a
    family-wise correction a dozen segments would produce a false alarm on most
    releases. Holm keeps the family-wise error rate at alpha and is uniformly
    more powerful than plain Bonferroni.
    """
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (m - rank) * p_values[index])
        running_max = max(running_max, candidate)
        adjusted[index] = running_max
    return adjusted
