"""News + People nodes via mocked Tavily."""

from __future__ import annotations

import respx
from httpx import Response

from backend.app.agent.nodes.news import run_news
from backend.app.agent.nodes.people import run_people
from backend.app.agent.runtime import RunContext
from backend.app.clients import close_http
from backend.app.schemas.state import AgentState, RunMeta

TAVILY_URL = "https://api.tavily.com/search"


async def test_news_collects_signals(broker, store) -> None:  # type: ignore[no-untyped-def]
    await close_http()
    state = AgentState(
        meta=RunMeta(company_url="https://acme.com", persona_name="P", persona_text="T")
    )
    await store.create_run(state.meta)
    ctx = RunContext(job_id=state.meta.job_id, broker=broker, store=store, trace=object())

    with respx.mock(assert_all_called=False) as router:
        router.post(TAVILY_URL).mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://news.example/acme-raises-30m",
                            "title": "Acme raises $30M",
                            "content": "Series B announcement.",
                            "score": 0.9,
                            "published_date": "2026-01-15",
                        }
                    ]
                },
            )
        )
        result = await run_news(state, ctx=ctx)
    assert result["news"].signals
    assert any("acme" in s.headline.lower() for s in result["news"].signals)
    await close_http()


async def test_news_handles_tavily_error(broker, store) -> None:  # type: ignore[no-untyped-def]
    await close_http()
    state = AgentState(
        meta=RunMeta(company_url="https://acme.com", persona_name="P", persona_text="T")
    )
    await store.create_run(state.meta)
    ctx = RunContext(job_id=state.meta.job_id, broker=broker, store=store, trace=object())
    with respx.mock(assert_all_called=False) as router:
        router.post(TAVILY_URL).mock(return_value=Response(500, text="boom"))
        result = await run_news(state, ctx=ctx)
    assert result["news"].signals == []
    await close_http()


async def test_people_extracts_name_title(broker, store) -> None:  # type: ignore[no-untyped-def]
    await close_http()
    state = AgentState(
        meta=RunMeta(company_url="https://acme.com", persona_name="P", persona_text="T")
    )
    await store.create_run(state.meta)
    ctx = RunContext(job_id=state.meta.job_id, broker=broker, store=store, trace=object())
    with respx.mock(assert_all_called=False) as router:
        router.post(TAVILY_URL).mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://www.linkedin.com/in/jane-smith/",
                            "title": "Jane Smith - VP Sales - Acme | LinkedIn",
                            "content": "Jane leads sales at Acme.",
                        }
                    ]
                },
            )
        )
        result = await run_people(state, ctx=ctx)
    names = [p.name for p in result["people"].people]
    assert "Jane Smith" in names
    await close_http()
