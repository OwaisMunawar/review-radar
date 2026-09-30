import pytest

from review_radar.domain.metrics import classification_report


def test_report_matches_hand_computed_values() -> None:
    labels = ["a", "b", "c"]
    expected = ["a", "a", "b", "b", "b"]
    predicted = ["a", "b", "b", "b", "c"]

    report = classification_report(expected, predicted, labels)

    assert report.accuracy == pytest.approx(3 / 5)
    assert report.confusion == ((1, 1, 0), (0, 2, 1), (0, 0, 0))
    a, b, c = report.per_class
    assert (a.precision, a.recall) == (1.0, 0.5)
    assert b.precision == pytest.approx(2 / 3)
    assert b.recall == pytest.approx(2 / 3)
    assert c.support == 0
    # c has no gold examples, so it does not dilute the macro average.
    assert report.macro_f1 == pytest.approx((a.f1 + b.f1) / 2)


def test_length_mismatch() -> None:
    with pytest.raises(ValueError, match="same length"):
        classification_report(["a"], [], ["a"])


def test_empty_input() -> None:
    report = classification_report([], [], ["a"])
    assert report.accuracy == 0.0
    assert report.macro_f1 == 0.0
