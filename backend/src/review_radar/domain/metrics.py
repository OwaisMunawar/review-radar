"""Classification metrics for the eval harness."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClassReport:
    label: str
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True, slots=True)
class ClassificationReport:
    labels: tuple[str, ...]
    accuracy: float
    macro_f1: float
    per_class: tuple[ClassReport, ...]
    # confusion[i][j] = cases whose expected label is labels[i] and predicted is labels[j]
    confusion: tuple[tuple[int, ...], ...]


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def classification_report(
    expected: Sequence[str], predicted: Sequence[str], labels: Sequence[str]
) -> ClassificationReport:
    """Accuracy, per-class P/R/F1 and macro-F1 over the classes present in `expected`.

    Macro-F1 averages over classes that appear in the gold labels only; including
    classes with zero support would reward a model for never predicting them.
    """
    if len(expected) != len(predicted):
        raise ValueError("expected and predicted must be the same length")
    index = {label: i for i, label in enumerate(labels)}
    size = len(labels)
    matrix = [[0] * size for _ in range(size)]
    for gold, guess in zip(expected, predicted, strict=True):
        matrix[index[gold]][index[guess]] += 1

    per_class: list[ClassReport] = []
    for i, label in enumerate(labels):
        tp = matrix[i][i]
        support = sum(matrix[i])
        predicted_count = sum(row[i] for row in matrix)
        precision = _safe_div(tp, predicted_count)
        recall = _safe_div(tp, support)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        per_class.append(ClassReport(label, precision, recall, f1, support))

    present = [c for c in per_class if c.support > 0]
    correct = sum(matrix[i][i] for i in range(size))
    return ClassificationReport(
        labels=tuple(labels),
        accuracy=_safe_div(correct, len(expected)),
        macro_f1=_safe_div(sum(c.f1 for c in present), len(present)),
        per_class=tuple(per_class),
        confusion=tuple(tuple(row) for row in matrix),
    )
