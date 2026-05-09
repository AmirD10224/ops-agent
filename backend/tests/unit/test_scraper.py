"""Scraper node, exercised with respx HTTP mocks."""

from __future__ import annotations

import respx
from httpx import Response

from backend.app.agent.nodes.scraper import _detect_company_name, run_scraper
from backend.app.agent.runtime import RunContext
from backend.app.clients import close_http
from backend.app.schemas.nodes import ScrapedPage
from backend.app.schemas.state import AgentState, RunMeta


def test_detect_company_name_splits_on_separator() -> None:
    pages = [
        ScrapedPage(
            url="https://x.com",  # type: ignore[arg-type]
            status=200,
            title="Acme. Build faster",
            text="...",
        )
    ]
    assert _detect_company_name(pages) == "Acme"


async def test_run_scraper_collects_pages(tmp_db_path: str, broker, store) -> None:  # type: ignore[no-untyped-def]
    await close_http()
    state = AgentState(
        meta=RunMeta(
            company_url="https://example.com",
            persona_name="P",
            persona_text="T",
        )
    )
    ctx = RunContext(job_id=state.meta.job_id, broker=broker, store=store, trace=object())
    # IMPORTANT: store needs a row to satisfy event FK.
    await store.create_run(state.meta)

    with respx.mock(assert_all_called=False) as router:
        router.get("https://example.com/").mock(
            return_value=Response(
                200,
                text="<html><head><title>Acme | Test</title></head><body>hi</body></html>",
                headers={"server": "cloudflare"},
            )
        )
        # All other paths 404
        router.get(url__regex=r"^https://example\.com/.+").mock(return_value=Response(404, text=""))
        result = await run_scraper(state, ctx=ctx)
    assert result["scrape"].canonical_domain == "example.com"
    assert any(p.title.startswith("Acme") for p in result["scrape"].pages)
    await close_http()


async def test_run_scraper_handles_no_pages(broker, store) -> None:  # type: ignore[no-untyped-def]
    await close_http()
    state = AgentState(
        meta=RunMeta(
            company_url="https://nothing.example",
            persona_name="P",
            persona_text="T",
        )
    )
    await store.create_run(state.meta)
    ctx = RunContext(job_id=state.meta.job_id, broker=broker, store=store, trace=object())
    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=r".*").mock(return_value=Response(500, text=""))
        result = await run_scraper(state, ctx=ctx)
    assert result["scrape"].pages == []
    await close_http()
