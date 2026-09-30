"""Reply publishers. The dry-run publisher is what demo mode and unconfigured stores use."""

from collections.abc import Mapping
from typing import Protocol

from review_radar.domain.errors import SourceNotConfiguredError
from review_radar.domain.models import Store


class _Replier(Protocol):
    async def reply(self, review_id: str, body: str) -> str: ...


class DryRunPublisher:
    @property
    def dry_run(self) -> bool:
        return True

    async def publish(self, *, store: Store, review_external_id: str, body: str) -> str | None:
        return None


class StorePublisher:
    def __init__(self, repliers: Mapping[Store, _Replier]) -> None:
        self._repliers = repliers

    @property
    def dry_run(self) -> bool:
        return False

    async def publish(self, *, store: Store, review_external_id: str, body: str) -> str | None:
        replier = self._repliers.get(store)
        if replier is None:
            raise SourceNotConfiguredError(f"{store.value} credentials are not configured")
        return await replier.reply(review_external_id, body)
