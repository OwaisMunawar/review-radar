import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from review_radar.adapters.stores import http as store_http
from review_radar.adapters.stores.app_store import (
    AppStoreConnectClient,
    AppStoreConnectSource,
    AppStoreCredentials,
    AppStoreToken,
    version_at,
)
from review_radar.adapters.stores.fixture import FixtureSource, load_dataset
from review_radar.adapters.stores.google_play import (
    GooglePlayClient,
    GooglePlaySource,
    ServiceAccount,
    parse_review,
)
from review_radar.adapters.stores.publisher import DryRunPublisher, StorePublisher
from review_radar.domain.errors import SourceNotConfiguredError, StoreApiError
from review_radar.domain.models import Store


def pem(key: ec.EllipticCurvePrivateKey | rsa.RSAPrivateKey) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr("review_radar.adapters.stores.http.asyncio.sleep", instant)


def test_dataset_is_fictional_and_covers_the_story() -> None:
    reviews = load_dataset()
    assert len(reviews) == 400
    versions = {r.app_version for r in reviews}
    assert versions == {"2.1.0", "2.2.0", "2.3.0", "2.3.1", "2.4.0"}
    assert {r.language for r in reviews} == {"en", "es", "de", "fr", "pt"}
    assert len({(r.store, r.external_id) for r in reviews}) == 400


async def test_fixture_source_filters_by_store_and_since() -> None:
    source = FixtureSource(Store.GOOGLE_PLAY)
    everything = [r async for r in source.fetch()]
    assert everything
    assert all(r.store is Store.GOOGLE_PLAY for r in everything)
    since = everything[-5].created_at
    assert len([r async for r in source.fetch(since=since)]) == 4
    assert source.name == "fixture:google_play"


async def test_fixture_source_reads_custom_path(tmp_path: Path) -> None:
    path = tmp_path / "set.json"
    item = {
        "store": "app_store",
        "external_id": "1",
        "rating": 5,
        "body": "ok",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    path.write_text(json.dumps({"reviews": [item]}))
    source = FixtureSource(Store.APP_STORE, path=path)
    assert [r.external_id async for r in source.fetch()] == ["1"]
    assert source.store is Store.APP_STORE


def test_app_store_token_claims_and_caching() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    now = [1_000_000.0]
    token = AppStoreToken(AppStoreCredentials("issuer", "KEY123", pem(key)), clock=lambda: now[0])
    first = token.get()
    claims = jwt.decode(
        first,
        key.public_key(),
        algorithms=["ES256"],
        audience="appstoreconnect-v1",
        options={"verify_exp": False},
    )
    assert claims["iss"] == "issuer"
    assert claims["exp"] - claims["iat"] == 1200
    assert jwt.get_unverified_header(first)["kid"] == "KEY123"
    now[0] += 60
    assert token.get() == first
    now[0] += 1200
    assert token.get() != first


def test_version_at_uses_latest_prior_release() -> None:
    history = [
        (datetime(2026, 1, 1, tzinfo=UTC), "2.2.0"),
        (datetime(2026, 2, 1, tzinfo=UTC), "2.3.0"),
    ]
    assert version_at(history, datetime(2025, 12, 1, tzinfo=UTC)) is None
    assert version_at(history, datetime(2026, 1, 15, tzinfo=UTC)) == "2.2.0"
    assert version_at(history, datetime(2026, 3, 1, tzinfo=UTC)) == "2.3.0"


def app_store_handler(calls: list[httpx.Request]) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["authorization"].startswith("Bearer ")
        path = request.url.path
        if path.endswith("/appStoreVersions"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "attributes": {
                                "versionString": "2.3.0",
                                "createdDate": "2026-05-01T00:00:00+00:00",
                            }
                        },
                        {
                            "attributes": {
                                "versionString": "2.2.0",
                                "createdDate": "2026-03-01T00:00:00+00:00",
                            }
                        },
                    ],
                    "links": {},
                },
            )
        if path.endswith("/customerReviews") and "cursor" not in str(request.url):
            if len([c for c in calls if c.url.path.endswith("/customerReviews")]) == 1:
                return httpx.Response(429, headers={"retry-after": "1"})
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "a1",
                            "attributes": {
                                "rating": 1,
                                "title": "Crash",
                                "body": "Crashes at login",
                                "reviewerNickname": "Kay",
                                "createdDate": "2026-05-06T10:00:00+00:00",
                                "territory": "USA",
                            },
                        }
                    ],
                    "links": {"next": "https://asc.test/v1/apps/42/customerReviews?cursor=2"},
                },
            )
        if path.endswith("/customerReviews"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "a0",
                            "attributes": {
                                "rating": 5,
                                "body": "Great",
                                "createdDate": "2026-03-10T10:00:00+00:00",
                            },
                        }
                    ],
                    "links": {},
                },
            )
        if path.endswith("/customerReviewResponses"):
            body = json.loads(request.content)
            assert body["data"]["relationships"]["review"]["data"]["id"] == "a1"
            return httpx.Response(201, json={"data": {"id": "resp-1"}})
        return httpx.Response(404)

    return handler


async def test_app_store_source_pages_retries_and_infers_versions() -> None:
    calls: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(app_store_handler(calls))) as http:
        key = ec.generate_private_key(ec.SECP256R1())
        client = AppStoreConnectClient(
            app_id="42",
            credentials=AppStoreCredentials("issuer", "KEY", pem(key)),
            client=http,
            base_url="https://asc.test",
        )
        source = AppStoreConnectSource(client)
        reviews = [r async for r in source.fetch()]
        assert [(r.external_id, r.app_version) for r in reviews] == [
            ("a1", "2.3.0"),
            ("a0", "2.2.0"),
        ]
        assert reviews[0].author == "Kay"
        assert source.store is Store.APP_STORE
        assert source.name == "app_store_connect"

        recent = [r async for r in source.fetch(since=datetime(2026, 4, 1, tzinfo=UTC))]
        assert [r.external_id for r in recent] == ["a1"]

        publisher = StorePublisher({Store.APP_STORE: client})
        assert not publisher.dry_run
        reply_id = await publisher.publish(
            store=Store.APP_STORE, review_external_id="a1", body="Hi"
        )
        assert reply_id == "resp-1"
        with pytest.raises(SourceNotConfiguredError):
            await publisher.publish(store=Store.GOOGLE_PLAY, review_external_id="x", body="Hi")


def play_review(
    review_id: str, text: str, seconds: int, version: str | None = "2.3.0"
) -> dict[str, Any]:
    comment: dict[str, Any] = {
        "text": text,
        "starRating": 2,
        "reviewerLanguage": "de_DE",
        "lastModified": {"seconds": str(seconds)},
    }
    if version:
        comment["appVersionName"] = version
    return {"reviewId": review_id, "authorName": "Jo", "comments": [{"userComment": comment}]}


async def test_google_play_source_authenticates_pages_and_replies() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    account = ServiceAccount(
        client_email="svc@proj.iam.test", private_key=pem(key), token_uri="https://oauth.test/token"
    )
    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        if request.url.host == "oauth.test":
            token_calls += 1
            form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
            claims = jwt.decode(
                form["assertion"],
                key.public_key(),
                algorithms=["RS256"],
                audience="https://oauth.test/token",
            )
            assert claims["iss"] == "svc@proj.iam.test"
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert request.headers["authorization"] == "Bearer tok"
        if request.url.path.endswith(":reply"):
            assert json.loads(request.content) == {"replyText": "Danke!"}
            return httpx.Response(200, json={"result": {"replyText": "Danke!"}})
        if request.url.params.get("token") == "p2":
            return httpx.Response(
                200, json={"reviews": [play_review("g2", "Stürzt ab", 1_780_000_000)]}
            )
        return httpx.Response(
            200,
            json={
                "reviews": [
                    play_review("g1", "Absturz\tStürzt beim Login ab", 1_790_000_000, version=None),
                    {"reviewId": "g0", "comments": [{"developerComment": {"text": "hi"}}]},
                ],
                "tokenPagination": {"nextPageToken": "p2"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = GooglePlayClient(
            package_name="app.pp", account=account, client=http, base_url="https://play.test/v3"
        )
        source = GooglePlaySource(client)
        reviews = [r async for r in source.fetch()]
        assert [r.external_id for r in reviews] == ["g1", "g2"]
        assert (reviews[0].title, reviews[0].body, reviews[0].language) == (
            "Absturz",
            "Stürzt beim Login ab",
            "de",
        )
        assert reviews[1].app_version == "2.3.0"
        assert token_calls == 1
        assert source.store is Store.GOOGLE_PLAY
        assert source.name == "google_play"
        assert await client.reply("g1", "Danke!") == "g1"


def test_parse_review_without_language() -> None:
    item = play_review("g", "Fine", 0)
    del item["comments"][0]["userComment"]["reviewerLanguage"]
    parsed = parse_review(item)
    assert parsed is not None
    assert parsed.language is None


def test_service_account_from_file(tmp_path: Path) -> None:
    path = tmp_path / "sa.json"
    path.write_text(json.dumps({"client_email": "a@b", "private_key": "not-a-real-key"}))
    account = ServiceAccount.from_file(path)
    assert account.token_uri.endswith("/token")
    assert "not-a-real-key" not in repr(account)


async def test_http_errors_become_typed_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/boom":
            raise httpx.ConnectError("down")
        return httpx.Response(403, text="forbidden")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(StoreApiError) as caught:
            await store_http.send(http, http.build_request("GET", "https://x.test/"))
        assert caught.value.details["status"] == 403
        with pytest.raises(StoreApiError, match="network"):
            await store_http.send(
                http, http.build_request("GET", "https://x.test/boom"), attempts=2
            )


async def test_dry_run_publisher() -> None:
    publisher = DryRunPublisher()
    assert publisher.dry_run
    assert await publisher.publish(store=Store.APP_STORE, review_external_id="1", body="x") is None
