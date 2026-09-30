"""Shared HTTP behaviour for store APIs: bounded retries on throttling and 5xx."""

import asyncio

import httpx
import structlog

from review_radar.domain.errors import StoreApiError

log = structlog.get_logger(__name__)

RETRYABLE = frozenset({429, 500, 502, 503, 504})


def _retry_after(response: httpx.Response, attempt: int, base_delay: float) -> float:
    header = response.headers.get("retry-after")
    if header and header.isdigit():
        return min(float(header), 60.0)
    return float(base_delay * 2**attempt)


async def send(
    client: httpx.AsyncClient,
    request: httpx.Request,
    *,
    attempts: int = 4,
    base_delay: float = 0.5,
) -> httpx.Response:
    for attempt in range(attempts):
        try:
            response = await client.send(request)
        except httpx.TransportError as exc:
            if attempt == attempts - 1:
                raise StoreApiError(f"network error calling {request.url.host}") from exc
            await asyncio.sleep(base_delay * 2**attempt)
            continue
        if response.status_code in RETRYABLE and attempt < attempts - 1:
            delay = _retry_after(response, attempt, base_delay)
            log.warning("store_api.retry", status=response.status_code, delay=delay)
            await asyncio.sleep(delay)
            continue
        if response.is_error:
            raise StoreApiError(
                f"{request.url.host} returned {response.status_code}",
                details={"status": response.status_code, "body": response.text[:500]},
            )
        return response
    raise StoreApiError("retries exhausted")  # pragma: no cover - loop always returns or raises
