"""NEWS node. Tavily search for recent buyer-relevant signals."""

from __future__ import annotations

import time
from datetime import date
from typing import Any
from urllib.parse import urlparse

from pydantic import HttpUrl

from backend.app.agent.runtime import RunContext
from backend.app.clients import TavilyError, tavily_search
from backend.app.logging_setup import get_logger
from backend.app.schemas.nodes import NewsResult
from backend.app.schemas.scorecard import NewsSignal
from backend.app.schemas.state import AgentState, ToolError

log = get_logger(__name__)


def _company_token(state: AgentState) -> str:
    if state.scrape and state.scrape.detected_name:
        return state.scrape.detected_name
    if state.scrape:
        return state.scrape.canonical_domain
    # No scrape data, derive a token from the URL host.
    raw = state.meta.company_url
    p = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (p.netloc or p.path).replace("www.", "").lower()
    return host.split(".")[0] or host or raw


def _parse_date(d: Any) -> date | None:
    if not isinstance(d, str):
        return None
    try:
        return date.fromisoformat(d[:10])
    except ValueError:
        return None


async def run_news(state: AgentState, *, ctx: RunContext) -> dict[str, NewsResult]:
    token = _company_token(state)
    queries = [
        f"{token} funding announcement 2026",
        f"{token} hiring product launch news",
        f"{token} layoffs OR acquisition OR partnership 2025",
    ]

    async with ctx.node("news", summary=f"news for {token}") as rec:
        signals: list[NewsSignal] = []
        used: list[str] = []
        for q in queries:
            t0 = time.perf_counter()
            try:
                resp = await tavily_search(q, max_results=5, days=365)
            except TavilyError as e:
                await ctx.tool_call(
                    node="news",
                    tool="tavily.search",
                    target=q,
                    success=False,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    error_message=str(e)[:200],
                )
                rec.error = ToolError(tool="tavily", message=str(e), retryable=True)
                continue
            await ctx.tool_call(
                node="news",
                tool="tavily.search",
                target=q,
                success=True,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            used.append(q)
            for r in resp.get("results", []) or []:
                url = r.get("url")
                title = r.get("title")
                if not url or not title:
                    continue
                try:
                    signals.append(
                        NewsSignal(
                            date=_parse_date(r.get("published_date") or r.get("date")),
                            headline=str(title)[:280],
                            url=HttpUrl(url),
                            buyer_relevance=str(r.get("content", ""))[:380] or "Recent mention",
                            confidence=min(0.85, float(r.get("score", 0.6))),
                        )
                    )
                except Exception as e:
                    log.debug("news.skip_row", error=str(e), url=url)

        # Deduplicate on URL, keep highest confidence.
        by_url: dict[str, NewsSignal] = {}
        for s in signals:
            key = str(s.url)
            if key not in by_url or s.confidence > by_url[key].confidence:
                by_url[key] = s
        deduped = sorted(by_url.values(), key=lambda x: x.confidence, reverse=True)[:10]
        rec.notes = f"{len(deduped)} signals, {len(used)} queries"

    return {"news": NewsResult(signals=deduped, queries_used=used)}
