import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from review_radar.adapters.llm.agents import build_models
from review_radar.cli import app
from review_radar.domain.models import (
    Category,
    LlmPurpose,
    LlmUsage,
    Sentiment,
    Severity,
    StoredReview,
    Triage,
)
from review_radar.evals.triage_eval import load_dataset, render, run_triage_eval


class AlwaysPraise:
    async def triage(self, review: StoredReview) -> tuple[Triage, LlmUsage]:
        triage = Triage(
            sentiment=Sentiment.POSITIVE,
            category=Category.PRAISE,
            severity=Severity.LOW,
            summary="Happy user",
        )
        return triage, LlmUsage(LlmPurpose.TRIAGE, "stub", 1, 1, Decimal(0), 1)


def test_dataset_is_balanced_enough() -> None:
    dataset = load_dataset()
    assert len(dataset.cases) == 60
    categories = {c.expected_output.category for c in dataset.cases if c.expected_output}
    assert categories == set(Category)


async def test_metrics_for_a_degenerate_model() -> None:
    result = await run_triage_eval(AlwaysPraise(), model_name="stub")
    assert result.category.accuracy == 8 / 60
    assert len(result.misses) == 52
    text = render(result)
    assert "macro-F1" in text
    assert "Misclassified" in text
    payload = result.to_json()
    assert payload["model"] == "stub"
    assert payload["measured_at"] == datetime.now(UTC).date().isoformat()


async def test_demo_model_clears_the_ci_threshold() -> None:
    result = await run_triage_eval(build_models("demo").triager, model_name="demo")
    assert result.failures == 0
    assert result.category.accuracy >= 0.85
    assert result.category.macro_f1 >= 0.85


def test_cli_eval_threshold_and_output(tmp_path: Path) -> None:
    out = tmp_path / "eval.json"
    runner = CliRunner()
    ok = runner.invoke(app, ["eval", "--model", "demo", "--min-accuracy", "0.5", "--out", str(out)])
    assert ok.exit_code == 0, ok.output
    assert json.loads(out.read_text())["cases"] == 60
    failing = runner.invoke(app, ["eval", "--model", "demo", "--min-accuracy", "0.99"])
    assert failing.exit_code == 1
