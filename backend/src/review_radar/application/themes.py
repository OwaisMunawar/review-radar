"""Cluster triage summaries into themes and name each one."""

from collections import Counter
from functools import partial

import structlog

from review_radar.application.ports import NewTheme, ThemeNamer, UnitOfWorkFactory
from review_radar.application.retry import with_retries
from review_radar.domain.clustering import agglomerate
from review_radar.domain.models import LlmUsage
from review_radar.domain.trend import classify_trend, weekly_buckets

log = structlog.get_logger(__name__)


class BuildThemes:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        namer: ThemeNamer,
        *,
        max_distance: float = 0.35,
        min_size: int = 4,
        weeks: int = 12,
        attempts: int = 3,
        sample: int = 25,
    ) -> None:
        self._uow = uow
        self._namer = namer
        self._max_distance = max_distance
        self._min_size = min_size
        self._weeks = weeks
        self._attempts = attempts
        self._sample = sample

    async def __call__(self) -> int:
        async with self._uow() as uow:
            embedded = await uow.triages.list_embedded()
        if not embedded:
            return 0

        clusters = agglomerate(
            [e.vector for e in embedded], max_distance=self._max_distance, min_size=self._min_size
        )
        # Anchor trends to the newest review rather than the wall clock, so an
        # imported backlog (or the demo dataset) shows its real shape.
        end = max(e.created_at for e in embedded)

        themes: list[NewTheme] = []
        usages: list[LlmUsage] = []
        for cluster in clusters:
            members = [embedded[i] for i in cluster.members]
            # Representatives first: the namer sees the most central wording.
            ordered = [embedded[i].summary for i in cluster.representatives] + [
                m.summary for m in members
            ]
            title, usage = await with_retries(
                partial(self._namer.name, ordered[: self._sample]),
                attempts=self._attempts,
            )
            usages.append(usage)
            weekly = weekly_buckets([m.created_at for m in members], end=end, weeks=self._weeks)
            themes.append(
                NewTheme(
                    title=title,
                    dominant_category=Counter(m.category for m in members).most_common(1)[0][0],
                    trend=classify_trend(weekly),
                    weekly_counts=weekly,
                    centroid=list(cluster.centroid),
                    member_ids=[m.review_id for m in members],
                    representative_ids=[embedded[i].review_id for i in cluster.representatives],
                )
            )

        async with self._uow() as uow:
            await uow.themes.replace_all(themes)
            for usage in usages:
                await uow.usage.record(usage)
            await uow.commit()
        log.info("themes.built", themes=len(themes), reviews=len(embedded))
        return len(themes)
