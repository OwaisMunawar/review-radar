import math

import pytest

from review_radar.domain.stats import holm_adjust, normal_sf, rate_ratio, two_proportion_z_test


def test_normal_sf_matches_known_quantiles() -> None:
    assert normal_sf(0.0) == pytest.approx(0.5)
    assert normal_sf(1.6448536) == pytest.approx(0.05, abs=1e-6)
    assert normal_sf(2.3263479) == pytest.approx(0.01, abs=1e-6)


def test_z_test_matches_hand_computed_value() -> None:
    # 10/100 vs 30/100: pooled p = 0.2, se = sqrt(0.2 * 0.8 * 0.02) = 0.05657
    result = two_proportion_z_test(10, 100, 30, 100)
    assert result.z == pytest.approx(0.2 / math.sqrt(0.2 * 0.8 * 0.02))
    assert result.p_value == pytest.approx(normal_sf(result.z))
    assert result.rate_ratio == pytest.approx(3.0)


def test_z_test_is_one_sided() -> None:
    assert two_proportion_z_test(30, 100, 10, 100).p_value > 0.99


def test_z_test_handles_degenerate_samples() -> None:
    result = two_proportion_z_test(0, 50, 0, 60)
    assert result.z == 0.0
    assert result.p_value == pytest.approx(0.5)


@pytest.mark.parametrize(("args"), [(0, 0, 1, 10), (5, 4, 1, 10), (-1, 10, 1, 10)])
def test_z_test_rejects_invalid_counts(args: tuple[int, int, int, int]) -> None:
    with pytest.raises(ValueError, match=r"sample|counts"):
        two_proportion_z_test(*args)


def test_rate_ratio_is_finite_when_baseline_is_zero() -> None:
    ratio = rate_ratio(0, 80, 12, 80)
    assert math.isfinite(ratio)
    assert ratio == pytest.approx((12.5 / 81) / (0.5 / 81))


def test_rate_ratio_nan_for_empty_sample() -> None:
    assert math.isnan(rate_ratio(1, 0, 1, 10))


def test_holm_adjust_matches_reference() -> None:
    # Reference values from R: p.adjust(c(0.01, 0.04, 0.03, 0.005), "holm")
    assert holm_adjust([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_holm_adjust_caps_at_one_and_handles_empty() -> None:
    assert holm_adjust([0.9, 0.8]) == [1.0, 1.0]
    assert holm_adjust([]) == []
