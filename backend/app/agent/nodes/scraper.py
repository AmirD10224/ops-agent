"""SCRAPER node, fetches homepage + a few high-signal pages."""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urljoin, urlparse

from pydantic import HttpUrl
from selectolax.parser import HTMLParser

from backend.app.agent.runtime import RunContext
from backend.app.clients import ScrapeError, fetch_url
from backend.app.logging_setup import get_logger
from backend.app.schemas.nodes import ScrapedPage, ScrapeResult
from backend.app.schemas.state import AgentState

log = get_logger(__name__)

# Pages we care about, in priority order. Probed in parallel; missing ones are skipped silently.
TARGET_PATHS = ["/", "/about", "/about-us", "/company", "/pricing", "/careers", "/jobs"]
MAX_TEXT_PER_PAGE = 18_000


def _normalize_root(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return f"{parsed.scheme or 'https'}://{parsed.netloc or parsed.path}"


def _domain_of(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    netloc = parsed.netloc or parsed.path
    return netloc.replace("www.", "").lower()


def _extract(html: str) -> tuple[str, str]:
    tree = HTMLParser(html)
    title_node = tree.css_first("title")
    title = title_node.text(strip=True) if title_node else ""
    for sel in ("script", "style", "nav", "footer", "noscript", "svg"):
        for n in tree.css(sel):
            n.decompose()
    body = tree.body
    text = body.text(separator=" ", strip=True) if body else ""
    text = " ".join(text.split())[:MAX_TEXT_PER_PAGE]
    return title, text


def _detect_company_name(pages: list[ScrapedPage]) -> str:
    for p in pages:
        if not p.title:
            continue
        # Common pattern: "Company. Tagline" or "Company | Tagline"
        for sep in (". ", " | ", " - ", " · "):
            if sep in p.title:
                head = p.title.split(sep, 1)[0].strip()
                if 1 < len(head) < 80:
                    return head
        if 1 < len(p.title) < 80:
            return p.title.strip()
    return ""


async def _try_fetch(ctx: RunContext, root: str, path: str) -> ScrapedPage | None:
    url = urljoin(root, path)
    t0 = time.perf_counter()
    try:
        resp = await fetch_url(url)
    except ScrapeError as e:
        await ctx.tool_call(
            node="scraper",
            tool="http.get",
            target=url,
            success=False,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            error_message=str(e)[:200],
        )
        return None
    duration_ms = int((time.perf_counter() - t0) * 1000)

    if resp.status_code >= 400:
        await ctx.tool_call(
            node="scraper",
            tool="http.get",
            target=url,
            success=False,
            duration_ms=duration_ms,
            error_message=f"http {resp.status_code}",
        )
        return None

    title, text = _extract(resp.text)
    headers = {
        k.lower(): v
        for k, v in resp.headers.items()
        if k.lower() in {"server", "x-powered-by", "via", "set-cookie", "content-type"}
    }
    await ctx.tool_call(
        node="scraper",
        tool="http.get",
        target=url,
        success=True,
        duration_ms=duration_ms,
    )
    return ScrapedPage(
        url=HttpUrl(str(resp.url)),
        status=resp.status_code,
        title=title,
        text=text,
        headers_seen=headers,
    )


async def run_scraper(state: AgentState, *, ctx: RunContext) -> dict[str, ScrapeResult]:
    root = _normalize_root(state.meta.company_url)
    domain = _domain_of(state.meta.company_url)

    async with ctx.node("scraper", summary=f"fetch {domain}") as rec:
        results = await asyncio.gather(
            *(_try_fetch(ctx, root, p) for p in TARGET_PATHS),
            return_exceptions=False,
        )
        # Keep at most one of each canonical path-after-redirect.
        seen: dict[str, ScrapedPage] = {}
        for page in results:
            if page is None:
                continue
            key = str(page.url).rstrip("/")
            seen.setdefault(key, page)
        pages = list(seen.values())
        detected = _detect_company_name(pages)
        rec.notes = f"{len(pages)} pages"
        if not pages:
            rec.mark_skipped("no pages reachable")
    return {
        "scrape": ScrapeResult(
            pages=pages,
            canonical_domain=domain,
            detected_name=detected,
        )
    }
