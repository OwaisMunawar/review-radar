"""The whole demo pipeline on the bundled dataset, against real Postgres.

This is the test that proves the README's story: the 2.3.0 auth change shows
up as a flagged regression, and 2.3.1 does not.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from review_radar.adapters.clock import SystemClock
from review_radar.adapters.db.read_model import SqlReadModel
from review_radar.adapters.llm.agents import build_models
from review_radar.adapters.llm.embeddings import build_embedder
from review_radar.adapters.stores.fixture import FixtureSource
from review_radar.application.ingest import IngestReviews
from review_radar.application.pipeline import Pipeline
from review_radar.application.releases import CompareReleases
from review_radar.application.replies import DraftReplies
from review_radar.application.themes import BuildThemes
from review_radar.application.triage import EmbedSummaries, TriageReviews
from review_radar.domain.errors import NotFoundError
from review_radar.domain.models import Store
from review_radar.domain.regression import SegmentKind
from tests.conftest import UowFactory


def demo_pipeline(uow: UowFactory) -> Pipeline:
    models = build_models("demo")
    return Pipeline(
        ingest=IngestReviews(
            uow, [FixtureSource(Store.APP_STORE), FixtureSource(Store.GOOGLE_PLAY)]
        ),
        triage=TriageReviews(uow, models.triager),
        embed=EmbedSummaries(uow, build_embedder("demo")),
        themes=BuildThemes(uow, models.theme_namer),
        draft=DraftReplies(uow, models.reply_writer, SystemClock()),
    )


async def test_demo_pipeline_finds_the_injected_regression(
    uow_factory: UowFactory, sessions: async_sessionmaker[AsyncSession]
) -> None:
    report = await demo_pipeline(uow_factory).run()
    assert report.ingested == 400
    assert report.triaged == 400
    assert report.embedded == 400
    assert report.drafted == 400
    assert report.themes >= 10

    read = SqlReadModel(sessions, model="demo", demo_mode=True)
    themes = await read.themes()
    titles = [t.title for t in themes]
    assert "App crashes when signing in" in titles

    compare = CompareReleases(read)
    regression = await compare("2.3.0")
    flagged = {s.label for s in regression.segments if s.flagged}
    assert "Crash" in flagged
    assert "App crashes when signing in" in flagged
    assert any(s.kind is SegmentKind.THEME and s.flagged for s in regression.segments)
    top = regression.segments[0]
    assert top.rate_ratio is not None
    assert top.rate_ratio > 5

    fixed = await compare("2.3.1")
    assert not any(s.flagged for s in fixed.segments)
    assert fixed.baseline.version == "2.3.0"

    latest = await compare()
    assert latest.candidate.version == "2.4.0"
    all_flags = await compare.all_flags()
    assert {f.headline.split(" up ")[0] for f in all_flags} >= {"Crash"}

    with pytest.raises(NotFoundError):
        await compare("9.9.9")
    with pytest.raises(NotFoundError):
        await compare("2.1.0")

    # A second run is a no-op: idempotent ingest, nothing left to triage or draft.
    again = await demo_pipeline(uow_factory).run()
    assert (again.ingested, again.triaged, again.drafted, again.themes) == (0, 0, 0, 0)


async def test_compare_without_data(sessions: async_sessionmaker[AsyncSession]) -> None:
    with pytest.raises(NotFoundError):
        await CompareReleases(SqlReadModel(sessions, model="demo", demo_mode=True))()
