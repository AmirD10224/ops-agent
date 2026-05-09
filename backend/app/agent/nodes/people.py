"""PEOPLE node, public-snippet search for decision-makers.

Honest constraints: we never scrape LinkedIn directly. Tavily returns search-result
snippets. We extract name+title from the snippet text only and mark each entry
with confidence < 1.0. No emails, no phones, no claims of personal data.
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlparse

from pydantic import HttpUrl, ValidationError

from backend.app.agent.runtime import RunContext
from backend.app.clients import TavilyError, tavily_search
from backend.app.logging_setup import get_logger
from backend.app.schemas.nodes import PeopleResult
from backend.app.schemas.scorecard import DecisionMaker
from backend.app.schemas.state import AgentState, ToolError

log = get_logger(__name__)

# Roles to search for. The synthesizer can re-rank these.
ROLE_QUERIES = ["CEO", 'CRO OR "VP Sales"', '"VP RevOps" OR "Head of Revenue Operations"']

# Pattern: "Name - Title - Company | LinkedIn" or "Name | Title at Company"
NAME_TITLE_RE = re.compile(
    r"(?P<name>[A-Z][a-zA-Z'.\-]{1,40}(?:\s[A-Z][a-zA-Z'.\-]{1,40}){0,3})"
    r"\s*[-–|·]\s*"
    r"(?P<title>[A-Z][^|·\n]{2,90}?)"
    r"(?:\s*[-–|·@]|$)"
)


def _company_token(state: AgentState) -> str:
    if state.scrape and state.scrape.detected_name:
        return state.scrape.detected_name
    if state.scrape:
        return state.scrape.canonical_domain
    raw = state.meta.company_url
    p = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (p.netloc or p.path).replace("www.", "").lower()
    return host.split(".")[0] or host or raw


def _parse_snippet(snippet: str) -> tuple[str, str] | None:
    m = NAME_TITLE_RE.search(snippet)
    if not m:
        return None
    name = m.group("name").strip()
    title = m.group("title").strip().rstrip(",.").strip()
    if len(name.split()) < 2 or len(title) < 3:
        return None
    return name, title


def _coerce_linkedin(url: str | None) -> HttpUrl | None:
    if not url or "linkedin.com/in/" not in url.lower():
        return None
    try:
        return HttpUrl(url)
    except ValidationError:
        return None


async def run_people(state: AgentState, *, ctx: RunContext) -> dict[str, PeopleResult]:
    token = _company_token(state)

    async with ctx.node("people", summary=f"people for {token}") as rec:
        people: list[DecisionMaker] = []
        used: list[str] = []
        for role in ROLE_QUERIES:
            query = f'"{token}" {role} site:linkedin.com/in'
            t0 = time.perf_counter()
            try:
                resp: dict[str, Any] = await tavily_search(
                    query,
                    max_results=4,
                    include_domains=["linkedin.com"],
                )
            except TavilyError as e:
                await ctx.tool_call(
                    node="people",
                    tool="tavily.search",
                    target=query,
                    success=False,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    error_message=str(e)[:200],
                )
                rec.error = ToolError(tool="tavily", message=str(e), retryable=True)
                continue
            await ctx.tool_call(
                node="people",
                tool="tavily.search",
                target=query,
                success=True,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            used.append(query)
            for r in resp.get("results", []) or []:
                snippet = (r.get("title") or "") + ". " + (r.get("content") or "")
                parsed = _parse_snippet(snippet)
                if not parsed:
                    continue
                name, title = parsed
                # Sanity: only keep if the company token appears in title or snippet.
                if token.lower() not in snippet.lower():
                    continue
                try:
                    people.append(
                        DecisionMaker(
                            name=name,
                            title=title,
                            linkedin=_coerce_linkedin(r.get("url")),
                            relevance=f"Public profile match for role: {role}",
                            confidence=0.55 if _coerce_linkedin(r.get("url")) else 0.35,
                        )
                    )
                except ValidationError as e:
                    log.debug("people.skip_row", error=str(e))

        # Dedupe on (name lower).
        seen: dict[str, DecisionMaker] = {}
        for p in people:
            key = p.name.lower()
            if key not in seen or p.confidence > seen[key].confidence:
                seen[key] = p
        deduped = sorted(seen.values(), key=lambda x: x.confidence, reverse=True)[:8]
        rec.notes = f"{len(deduped)} candidates, {len(used)} queries"

    return {"people": PeopleResult(people=deduped, queries_used=used)}
