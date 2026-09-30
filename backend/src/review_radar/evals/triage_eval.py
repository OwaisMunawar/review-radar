"""Triage evaluation on the hand-labelled set, built on pydantic_evals.

pydantic_evals runs the task and the per-case evaluators; the aggregate
metrics (macro-F1, confusion matrix) come from domain.metrics so they are
unit-tested and identical across model runs.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from uuid import uuid4

from pydantic import BaseModel
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from review_radar.application.ports import ReviewTriager
from review_radar.domain.metrics import ClassificationReport, classification_report
from review_radar.domain.models import Category, Sentiment, Store, StoredReview


class ReviewInput(BaseModel):
    text: str
    rating: int


class Label(BaseModel):
    category: Category
    sentiment: Sentiment


@dataclass
class CategoryMatch(Evaluator[ReviewInput, Label]):
    def evaluate(self, ctx: EvaluatorContext[ReviewInput, Label]) -> bool:
        return (
            ctx.expected_output is not None and ctx.output.category == ctx.expected_output.category
        )


@dataclass
class SentimentMatch(Evaluator[ReviewInput, Label]):
    def evaluate(self, ctx: EvaluatorContext[ReviewInput, Label]) -> bool:
        return (
            ctx.expected_output is not None
            and ctx.output.sentiment == ctx.expected_output.sentiment
        )


def load_dataset() -> Dataset[ReviewInput, Label]:
    raw = json.loads(
        resources.files("review_radar.data").joinpath("eval_reviews.json").read_text("utf-8")
    )
    cases = [
        Case(
            name=item["id"],
            inputs=ReviewInput(text=item["text"], rating=item["rating"]),
            expected_output=Label(category=item["category"], sentiment=item["sentiment"]),
        )
        for item in raw["cases"]
    ]
    return Dataset(name="triage", cases=cases, evaluators=[CategoryMatch(), SentimentMatch()])


@dataclass(frozen=True, slots=True)
class Miss:
    case: str
    text: str
    expected: str
    predicted: str


@dataclass(frozen=True, slots=True)
class EvalResult:
    model: str
    cases: int
    failures: int
    category: ClassificationReport
    sentiment: ClassificationReport
    misses: list[Miss]

    def to_json(self) -> dict[str, object]:
        def summary(report: ClassificationReport) -> dict[str, object]:
            return {
                "accuracy": round(report.accuracy, 4),
                "macro_f1": round(report.macro_f1, 4),
                "labels": list(report.labels),
                "confusion": [list(row) for row in report.confusion],
            }

        return {
            "model": self.model,
            "cases": self.cases,
            "failures": self.failures,
            "measured_at": datetime.now(UTC).date().isoformat(),
            "category": summary(self.category),
            "sentiment": summary(self.sentiment),
        }


async def run_triage_eval(
    triager: ReviewTriager, *, model_name: str, concurrency: int = 4
) -> EvalResult:
    dataset = load_dataset()

    async def task(inputs: ReviewInput) -> Label:
        review = StoredReview(
            id=uuid4(),
            store=Store.GOOGLE_PLAY,
            external_id="eval",
            rating=inputs.rating,
            body=inputs.text,
            created_at=datetime.now(UTC),
        )
        triage, _ = await triager.triage(review)
        return Label(category=triage.category, sentiment=triage.sentiment)

    report = await dataset.evaluate(task, max_concurrency=concurrency, progress=False)
    by_name = {c.name: c for c in report.cases}
    ordered = [by_name[c.name] for c in dataset.cases if c.name in by_name]

    expected = [c.expected_output for c in ordered if c.expected_output is not None]
    predicted = [c.output for c in ordered]
    misses = [
        Miss(
            case=c.name,
            text=c.inputs.text,
            expected=c.expected_output.category.value,
            predicted=c.output.category.value,
        )
        for c in ordered
        if c.expected_output is not None and c.output.category != c.expected_output.category
    ]
    return EvalResult(
        model=model_name,
        cases=len(dataset.cases),
        failures=len(report.failures),
        category=classification_report(
            [e.category.value for e in expected],
            [p.category.value for p in predicted],
            [c.value for c in Category],
        ),
        sentiment=classification_report(
            [e.sentiment.value for e in expected],
            [p.sentiment.value for p in predicted],
            [s.value for s in Sentiment],
        ),
        misses=misses,
    )


def render(result: EvalResult) -> str:
    """Plain-text report: headline metrics, confusion matrix, misses."""
    short = {
        "crash": "crash",
        "performance": "perf",
        "login": "login",
        "payments": "pay",
        "ux": "ux",
        "feature_request": "feat",
        "praise": "praise",
        "other": "other",
    }
    cat, sen = result.category, result.sentiment
    lines = [
        f"Triage eval: {result.cases} cases, model={result.model}, failures={result.failures}",
        "",
        f"  category   accuracy {cat.accuracy:6.1%}   macro-F1 {cat.macro_f1:.3f}",
        f"  sentiment  accuracy {sen.accuracy:6.1%}   macro-F1 {sen.macro_f1:.3f}",
        "",
        "Category confusion (rows = expected, columns = predicted)",
        "  " + " " * 8 + "".join(f"{short[label]:>7}" for label in cat.labels),
    ]
    for label, row in zip(cat.labels, cat.confusion, strict=True):
        lines.append(f"  {short[label]:<8}" + "".join(f"{n:>7}" for n in row))
    lines += ["", "Per-category F1"]
    lines += [f"  {c.label:<16} {c.f1:.2f}  (n={c.support})" for c in cat.per_class if c.support]
    if result.misses:
        lines += ["", "Misclassified"]
        lines += [
            f"  {m.case}  expected {m.expected:<15} got {m.predicted:<15} {m.text[:60]}"
            for m in result.misses
        ]
    return "\n".join(lines)
