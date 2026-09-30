"""Offline review source backed by the bundled synthetic dataset."""

import json
from collections.abc import AsyncIterator
from datetime import datetime
from importlib import resources
from pathlib import Path

from review_radar.domain.models import IncomingReview, Store

DEFAULT_DATASET = "pocket_planner_reviews.json"


def load_dataset(path: Path | None = None) -> list[IncomingReview]:
    if path is None:
        raw = resources.files("review_radar.data").joinpath(DEFAULT_DATASET).read_text("utf-8")
    else:
        raw = path.read_text("utf-8")
    return [
        IncomingReview(
            store=Store(item["store"]),
            external_id=item["external_id"],
            rating=item["rating"],
            body=item["body"],
            created_at=datetime.fromisoformat(item["created_at"]),
            title=item.get("title"),
            language=item.get("language"),
            app_version=item.get("app_version"),
            territory=item.get("territory"),
            author=item.get("author"),
        )
        for item in json.loads(raw)["reviews"]
    ]


class FixtureSource:
    """Replays a JSON dataset as if it came from one store."""

    def __init__(self, store: Store, *, path: Path | None = None) -> None:
        self._store = store
        self._path = path

    @property
    def store(self) -> Store:
        return self._store

    @property
    def name(self) -> str:
        return f"fixture:{self._store.value}"

    async def fetch(self, *, since: datetime | None = None) -> AsyncIterator[IncomingReview]:
        for review in load_dataset(self._path):
            if review.store is self._store and (since is None or review.created_at > since):
                yield review
