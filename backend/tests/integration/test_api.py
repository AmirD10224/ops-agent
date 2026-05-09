"""HTTP surface, startup, validation, /personas, error paths."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch, tmp_db_path: str) -> AsyncClient:
    monkeypatch.setenv("SQLITE_PATH", tmp_db_path)
    from backend.app.config import get_settings

    get_settings.cache_clear()
    from backend.app import store as store_mod

    store_mod._store = None

    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Manually trigger lifespan startup tasks.
        async with app.router.lifespan_context(app):
            yield ac


async def test_healthz(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_personas(client: AsyncClient) -> None:
    r = await client.get("/personas")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["personas"]}
    assert "ae_series_b_saas" in ids


async def test_research_validates_payload(client: AsyncClient) -> None:
    r = await client.post("/research", json={})
    assert r.status_code == 422  # missing company_url


async def test_research_requires_persona(client: AsyncClient) -> None:
    r = await client.post("/research", json={"company_url": "https://x.com"})
    assert r.status_code == 400


async def test_research_404_for_unknown_job(client: AsyncClient) -> None:
    r = await client.get("/research/nope")
    assert r.status_code == 404


async def test_traces_empty(client: AsyncClient) -> None:
    r = await client.get("/traces")
    assert r.status_code == 200
    assert r.json() == {"runs": []}
