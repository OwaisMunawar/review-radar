"""End-to-end run used by `review-radar seed` and scheduled jobs."""

from dataclasses import dataclass
from datetime import datetime

from review_radar.application.ingest import IngestReviews
from review_radar.application.replies import DraftReplies
from review_radar.application.themes import BuildThemes
from review_radar.application.triage import EmbedSummaries, TriageReviews
from review_radar.application.views import PipelineReport


@dataclass(frozen=True, slots=True)
class Pipeline:
    ingest: IngestReviews
    triage: TriageReviews
    embed: EmbedSummaries
    themes: BuildThemes
    draft: DraftReplies

    async def run(self, *, since: datetime | None = None, draft_limit: int = 500) -> PipelineReport:
        ingested = await self.ingest(since=since)
        triaged = await self.triage()
        embedded = await self.embed()
        # Rebuild themes only when something new was embedded; clustering is
        # deterministic, so an unchanged input would produce the same themes.
        themes = await self.themes() if embedded or ingested.inserted else 0
        drafted = await self.draft(limit=draft_limit)
        return PipelineReport(
            ingested=ingested.inserted,
            updated=ingested.updated,
            triaged=triaged.triaged,
            triage_failures=triaged.failed,
            embedded=embedded,
            themes=themes,
            drafted=drafted,
        )
