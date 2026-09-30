from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from review_radar.api.app import create_app
from review_radar.config import Settings
from review_radar.container import Container, build_container

ORIGIN = "http://localhost:5173"


@pytest.fixture
async def container(
    migrated: str, sessions: async_sessionmaker[AsyncSession]
) -> AsyncIterator[Container]:
    settings = Settings(database_url=migrated, model="demo", cors_origins=[ORIGIN])
    async with build_container(settings) as container:
        yield container


@pytest.fixture
async def client(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(container.settings)
    # ASGITransport skips lifespan, so attach the container the lifespan would build.
    app.state.container = container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def seed(container: Container) -> None:
    await container.pipeline(container.fixture_sources()).run()


async def test_health_and_empty_overview(client: httpx.AsyncClient) -> None:
    health = (await client.get("/api/health")).json()
    assert health == {
        "status": "ok",
        "version": "0.1.0",
        "database": True,
        "model": "demo",
        "demo_mode": True,
    }
    overview = (await client.get("/api/overview")).json()
    assert overview["total_reviews"] == 0
    assert overview["negative_share"] is None


async def test_dashboard_reads(client: httpx.AsyncClient, container: Container) -> None:
    await seed(container)
    overview = (await client.get("/api/overview", params={"weeks": 52})).json()
    assert overview["total_reviews"] == 400
    assert overview["pending_replies"] == 400
    assert 0 < overview["negative_share"] < 1
    assert overview["weekly"][-1]["week_start"] <= "2026-09-28"

    themes = (await client.get("/api/themes")).json()
    assert len(themes) >= 10
    assert all(len(t["weekly_counts"]) == 12 for t in themes)

    page = (
        await client.get(
            "/api/reviews", params={"category": "crash", "version": "2.3.0", "limit": 5}
        )
    ).json()
    assert page["total"] >= 15
    assert len(page["items"]) == 5
    first = page["items"][0]
    assert first["triage"]["category"] == "crash"

    detail = await client.get(f"/api/reviews/{first['id']}")
    assert detail.json()["id"] == first["id"]
    similar = (await client.get(f"/api/reviews/{first['id']}/similar")).json()
    assert len(similar) == 5
    assert similar[0]["triage"]["category"] == "crash"

    releases = (await client.get("/api/releases")).json()
    assert [r["version"] for r in releases] == ["2.1.0", "2.2.0", "2.3.0", "2.3.1", "2.4.0"]

    comparison = (await client.get("/api/releases/compare", params={"candidate": "2.3.0"})).json()
    assert comparison["baseline"]["version"] == "2.2.0"
    assert comparison["segments"][0]["flagged"] is True

    flags = (await client.get("/api/releases/regressions")).json()
    assert any("2.3.0" in f["headline"] for f in flags)


async def test_reply_workflow(client: httpx.AsyncClient, container: Container) -> None:
    await seed(container)
    queue = (await client.get("/api/replies", params={"state": "draft", "limit": 3})).json()
    assert queue["total"] == 400
    reply = queue["items"][0]
    # The queue is ordered by severity, so the first item is critical.
    assert reply["review"]["triage"]["severity"] == "critical"
    rid = reply["id"]

    early = await client.post(f"/api/replies/{rid}/post", json={"actor": "dana"})
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "invalid_transition"

    too_long = "x" * (reply["char_limit"] + 1)
    bad = await client.post(f"/api/replies/{rid}/edit", json={"actor": "dana", "body": too_long})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "reply_invalid"

    edited = await client.post(f"/api/replies/{rid}/edit", json={"actor": "dana", "body": "Fixed!"})
    assert edited.json()["state"] == "edited"
    posted = (await client.post(f"/api/replies/{rid}/post", json={"actor": "dana"})).json()
    assert posted["state"] == "would_post"
    assert [a["action"] for a in posted["audit"]] == ["draft", "edit", "dry_run_post"]

    other = queue["items"][1]["id"]
    rejected = await client.post(
        f"/api/replies/{other}/reject", json={"actor": "dana", "note": "no"}
    )
    assert rejected.json()["state"] == "rejected"
    redrafted = await client.post(f"/api/replies/{other}/redraft", json={"actor": "dana"})
    assert redrafted.json()["state"] == "draft"
    approved = await client.post(f"/api/replies/{other}/approve", json={"actor": "dana"})
    assert approved.json()["approved_by"] == "dana"
    assert (await client.get(f"/api/replies/{other}")).json()["state"] == "approved"


@pytest.mark.parametrize(
    ("method", "url", "body", "status", "code"),
    [
        ("get", "/api/reviews?limit=0", None, 422, "validation_error"),
        ("get", "/api/reviews?rating=9", None, 422, "validation_error"),
        ("get", "/api/reviews/not-a-uuid", None, 422, "validation_error"),
        ("get", "/api/reviews/00000000-0000-0000-0000-000000000000", None, 404, "not_found"),
        ("get", "/api/replies/00000000-0000-0000-0000-000000000000", None, 404, "not_found"),
        ("get", "/api/releases/compare?candidate=1.0;drop", None, 422, "validation_error"),
        ("get", "/api/releases/compare", None, 404, "not_found"),
        (
            "post",
            "/api/replies/00000000-0000-0000-0000-000000000000/approve",
            {"actor": "<script>"},
            422,
            "validation_error",
        ),
        (
            "post",
            "/api/replies/00000000-0000-0000-0000-000000000000/approve",
            {"actor": "dana"},
            404,
            "not_found",
        ),
    ],
)
async def test_errors_share_one_envelope(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    body: dict[str, Any] | None,
    status: int,
    code: str,
) -> None:
    response = await client.request(method, url, json=body)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


async def test_cors_is_locked_to_configured_origins(client: httpx.AsyncClient) -> None:
    headers = {"Access-Control-Request-Method": "POST"}
    allowed = await client.options("/api/overview", headers={**headers, "Origin": ORIGIN})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    denied = await client.options(
        "/api/overview", headers={**headers, "Origin": "https://evil.example"}
    )
    assert "access-control-allow-origin" not in denied.headers


async def test_unexpected_errors_are_opaque(container: Container) -> None:
    app = create_app(container.settings)
    app.state.container = container

    @app.get("/api/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.get("/api/boom")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "unexpected error", "details": {}}
    }
