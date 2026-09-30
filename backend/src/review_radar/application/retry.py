import asyncio
from collections.abc import Awaitable, Callable

import structlog

from review_radar.domain.errors import LlmError

log = structlog.get_logger(__name__)


async def with_retries[T](
    call: Callable[[], Awaitable[T]], *, attempts: int, base_delay: float = 0.5
) -> T:
    """Retry model calls on LlmError with exponential backoff.

    PydanticAI already re-prompts on invalid structured output; this layer
    covers provider-side failures (rate limits, timeouts, 5xx) that surface as
    LlmError from the adapters.
    """
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except LlmError as exc:
            if attempt == attempts:
                raise
            delay = base_delay * 2 ** (attempt - 1)
            log.warning("llm.retry", attempt=attempt, delay=delay, error=exc.message)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
