"""App Store Connect API: customer reviews and developer responses.

Auth is a short-lived ES256 JWT signed with an API key from App Store Connect
(Users and Access > Integrations). Docs:
https://developer.apple.com/documentation/appstoreconnectapi/customer-reviews
"""

import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import jwt

from review_radar.adapters.stores.http import send
from review_radar.domain.models import IncomingReview, Store
from review_radar.domain.versions import version_key

BASE_URL = "https://api.appstoreconnect.apple.com"
TOKEN_TTL = 20 * 60  # Apple rejects tokens that live longer than 20 minutes.


@dataclass(frozen=True, slots=True)
class AppStoreCredentials:
    issuer_id: str
    key_id: str
    private_key_pem: str


class AppStoreToken:
    def __init__(
        self, credentials: AppStoreCredentials, *, clock: Callable[[], float] = time.time
    ) -> None:
        self._credentials = credentials
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    def get(self) -> str:
        now = float(self._clock())
        if self._token is None or now > self._expires_at - 60:
            issued = int(now)
            self._expires_at = issued + TOKEN_TTL
            self._token = jwt.encode(
                {
                    "iss": self._credentials.issuer_id,
                    "iat": issued,
                    "exp": issued + TOKEN_TTL,
                    "aud": "appstoreconnect-v1",
                },
                self._credentials.private_key_pem,
                algorithm="ES256",
                headers={"kid": self._credentials.key_id, "typ": "JWT"},
            )
        return self._token


class AppStoreConnectClient:
    def __init__(
        self,
        *,
        app_id: str,
        credentials: AppStoreCredentials,
        client: httpx.AsyncClient,
        base_url: str = BASE_URL,
    ) -> None:
        self._app_id = app_id
        self._token = AppStoreToken(credentials)
        self._client = client
        self._base = base_url

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Request:
        headers = {"Authorization": f"Bearer {self._token.get()}"}
        return self._client.build_request(method, url, headers=headers, **kwargs)

    async def _get(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        response = await send(self._client, self._request("GET", url, params=params))
        data: dict[str, Any] = response.json()
        return data

    async def release_history(self) -> list[tuple[datetime, str]]:
        """(created date, version string) for every App Store version, oldest first."""
        url: str | None = f"{self._base}/v1/apps/{self._app_id}/appStoreVersions"
        params: dict[str, str] | None = {
            "fields[appStoreVersions]": "versionString,createdDate",
            "limit": "200",
        }
        history: list[tuple[datetime, str]] = []
        while url:
            page = await self._get(url, params)
            for item in page.get("data", []):
                attrs = item.get("attributes", {})
                if attrs.get("createdDate") and attrs.get("versionString"):
                    created = datetime.fromisoformat(attrs["createdDate"])
                    history.append((created, attrs["versionString"]))
            url, params = page.get("links", {}).get("next"), None
        return sorted(history, key=lambda h: (h[0], version_key(h[1])))

    async def reviews(self) -> AsyncIterator[dict[str, Any]]:
        url: str | None = f"{self._base}/v1/apps/{self._app_id}/customerReviews"
        params: dict[str, str] | None = {"sort": "-createdDate", "limit": "200"}
        while url:
            page = await self._get(url, params)
            for item in page.get("data", []):
                yield item
            url, params = page.get("links", {}).get("next"), None

    async def reply(self, review_id: str, body: str) -> str:
        payload = {
            "data": {
                "type": "customerReviewResponses",
                "attributes": {"responseBody": body},
                "relationships": {"review": {"data": {"type": "customerReviews", "id": review_id}}},
            }
        }
        url = f"{self._base}/v1/customerReviewResponses"
        response = await send(self._client, self._request("POST", url, json=payload), attempts=1)
        return str(response.json()["data"]["id"])


def version_at(history: list[tuple[datetime, str]], moment: datetime) -> str | None:
    """Best guess at the version a reviewer was running.

    The customer reviews resource carries no version, so we attribute each
    review to the newest version record created before it. That can be early by
    the length of App Review; docs/ARCHITECTURE.md covers the trade-off.
    """
    current: str | None = None
    for created, version in history:
        if created <= moment:
            current = version
        else:
            break
    return current


class AppStoreConnectSource:
    def __init__(self, client: AppStoreConnectClient) -> None:
        self._client = client

    @property
    def store(self) -> Store:
        return Store.APP_STORE

    @property
    def name(self) -> str:
        return "app_store_connect"

    async def fetch(self, *, since: datetime | None = None) -> AsyncIterator[IncomingReview]:
        history = await self._client.release_history()
        async for item in self._client.reviews():
            attrs = item["attributes"]
            created = datetime.fromisoformat(attrs["createdDate"])
            if since is not None and created <= since:
                # Sorted newest first, so everything after this is older still.
                return
            yield IncomingReview(
                store=Store.APP_STORE,
                external_id=str(item["id"]),
                rating=int(attrs["rating"]),
                title=attrs.get("title"),
                body=attrs.get("body") or "",
                created_at=created,
                territory=attrs.get("territory"),
                author=attrs.get("reviewerNickname"),
                app_version=version_at(history, created),
            )
