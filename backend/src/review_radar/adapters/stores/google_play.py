"""Google Play Developer API: reviews and replies.

Auth uses a service account with access to the app in Play Console, exchanged
for an OAuth access token via the JWT bearer grant. The API only returns
reviews from the last week, so ingestion should run at least daily. Docs:
https://developers.google.com/android-publisher/reply-to-reviews
"""

import json
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jwt
from pydantic import BaseModel, SecretStr

from review_radar.adapters.stores.http import send
from review_radar.domain.models import IncomingReview, Store

BASE_URL = "https://androidpublisher.googleapis.com/androidpublisher/v3"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"


class ServiceAccount(BaseModel):
    client_email: str
    private_key: SecretStr
    token_uri: str = "https://oauth2.googleapis.com/token"  # noqa: S105 - a URL, not a secret

    @classmethod
    def from_file(cls, path: Path) -> "ServiceAccount":
        return cls.model_validate(json.loads(path.read_text()))


class GooglePlayClient:
    def __init__(
        self,
        *,
        package_name: str,
        account: ServiceAccount,
        client: httpx.AsyncClient,
        base_url: str = BASE_URL,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._package = package_name
        self._account = account
        self._client = client
        self._base = base_url
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    async def _access_token(self) -> str:
        now = float(self._clock())
        if self._token is not None and now < self._expires_at - 60:
            return self._token
        assertion = jwt.encode(
            {
                "iss": self._account.client_email,
                "scope": SCOPE,
                "aud": self._account.token_uri,
                "iat": int(now),
                "exp": int(now) + 3600,
            },
            self._account.private_key.get_secret_value(),
            algorithm="RS256",
        )
        request = self._client.build_request(
            "POST",
            self._account.token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        body = (await send(self._client, request)).json()
        self._token = str(body["access_token"])
        self._expires_at = now + float(body.get("expires_in", 3600))
        return self._token

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Request:
        headers = {"Authorization": f"Bearer {await self._access_token()}"}
        return self._client.build_request(method, url, headers=headers, **kwargs)

    async def reviews(self) -> AsyncIterator[dict[str, Any]]:
        url = f"{self._base}/applications/{self._package}/reviews"
        token: str | None = None
        while True:
            params = {"maxResults": "100"}
            if token:
                params["token"] = token
            page = (await send(self._client, await self._request("GET", url, params=params))).json()
            for item in page.get("reviews", []):
                yield item
            token = page.get("tokenPagination", {}).get("nextPageToken")
            if not token:
                return

    async def reply(self, review_id: str, body: str) -> str:
        url = f"{self._base}/applications/{self._package}/reviews/{review_id}:reply"
        request = await self._request("POST", url, json={"replyText": body})
        await send(self._client, request, attempts=1)
        # Play keeps one reply per review and returns no id, so the review id is the handle.
        return review_id


def parse_review(item: dict[str, Any]) -> IncomingReview | None:
    comments = [c["userComment"] for c in item.get("comments", []) if "userComment" in c]
    if not comments:
        return None
    comment = comments[0]
    text = str(comment.get("text", "")).strip()
    # Reviews with a title come back as "title\tbody".
    title, _, rest = text.partition("\t")
    title_part, body = (title, rest) if rest else (None, text)
    modified = comment.get("lastModified", {})
    created = datetime.fromtimestamp(int(modified.get("seconds", 0)), tz=UTC)
    language = comment.get("reviewerLanguage")
    return IncomingReview(
        store=Store.GOOGLE_PLAY,
        external_id=str(item["reviewId"]),
        rating=int(comment["starRating"]),
        title=title_part,
        body=body.strip(),
        created_at=created,
        language=language.split("_")[0].lower() if language else None,
        app_version=comment.get("appVersionName"),
        author=item.get("authorName"),
    )


class GooglePlaySource:
    def __init__(self, client: GooglePlayClient) -> None:
        self._client = client

    @property
    def store(self) -> Store:
        return Store.GOOGLE_PLAY

    @property
    def name(self) -> str:
        return "google_play"

    async def fetch(self, *, since: datetime | None = None) -> AsyncIterator[IncomingReview]:
        async for item in self._client.reviews():
            review = parse_review(item)
            if review is not None and (since is None or review.created_at > since):
                yield review
