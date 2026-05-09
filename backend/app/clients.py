"""Outbound clients. Anthropic, Tavily, HTTP. Wrapped with retry + structured errors."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from anthropic import AsyncAnthropic
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from backend.app.config import get_settings
from backend.app.logging_setup import get_logger

log = get_logger(__name__)


class TavilyError(RuntimeError):
    pass


class ScrapeError(RuntimeError):
    pass


def _retry_policy(attempts: int = 3) -> AsyncRetrying:
    # ``httpx.TimeoutException`` is a subclass of ``httpx.HTTPError`` already;
    # listing only HTTPError keeps the predicate honest.
    return AsyncRetrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential_jitter(initial=0.5, max=4.0),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )


_anthropic: AsyncAnthropic | None = None


def get_anthropic() -> AsyncAnthropic:
    """Singleton Anthropic client.

    The LLM wrapper (``agent/llm.py``) already does its own one-shot JSON
    repair retry; we leave SDK-level ``max_retries`` at 0 to keep retry
    budgets explicit and prevent compounding.
    """
    global _anthropic
    if _anthropic is None:
        settings = get_settings()
        _anthropic = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            max_retries=0,
            timeout=60.0,
        )
    return _anthropic


def reset_anthropic_for_tests() -> None:
    global _anthropic
    _anthropic = None


_http: httpx.AsyncClient | None = None


def get_http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        settings = get_settings()
        _http = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "OpsAgent/0.1 (+https://github.com/) research-bot; respects robots.txt"
                )
            },
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _http


async def close_http() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


async def fetch_url(url: str) -> httpx.Response:
    """GET with retries + structured error on permanent failure."""
    client = get_http()
    try:
        async for attempt in _retry_policy(attempts=3):
            with attempt:
                resp = await client.get(url)
                # 4xx is permanent, don't retry, but don't raise either; let callers decide.
                return resp
    except httpx.HTTPError as e:
        # tenacity reraises the underlying exception (not RetryError) when
        # ``reraise=True`` and attempts are exhausted.
        raise ScrapeError(f"fetch failed after retries: {url}") from e
    raise ScrapeError(f"fetch unreachable: {url}")  # pragma: no cover


async def tavily_search(
    query: str,
    *,
    max_results: int | None = None,
    include_domains: list[str] | None = None,
    days: int | None = None,
) -> dict[str, Any]:
    """Tavily search via REST. Returns the raw response or raises TavilyError.

    We hit the REST endpoint directly rather than the SDK so we control timeouts,
    retries, and error semantics consistently with the rest of the stack.
    """
    settings = get_settings()
    api_key = settings.tavily_api_key.get_secret_value()
    if not api_key:
        raise TavilyError("TAVILY_API_KEY missing")

    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results or settings.tavily_max_results,
        "search_depth": "basic",
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if days is not None:
        payload["days"] = days

    client = get_http()
    try:
        async for attempt in _retry_policy(attempts=3):
            with attempt:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json=payload,
                    timeout=settings.http_timeout_seconds,
                )
                if resp.status_code >= 500:
                    resp.raise_for_status()  # triggers retry
                if resp.status_code >= 400:
                    # 4xx is non-retryable; the response body could echo the
                    # API key on auth errors so we never include resp.text.
                    raise TavilyError(f"tavily {resp.status_code}")
                return resp.json()  # type: ignore[no-any-return]
    except httpx.HTTPError as e:
        # After ``reraise=True`` exhausts retries, the original HTTPError
        # propagates here.
        raise TavilyError(f"tavily failed after retries: {query}") from e
    raise TavilyError("tavily unreachable")  # pragma: no cover


async def aclose_all() -> None:
    """Call on app shutdown."""
    await close_http()
    global _anthropic
    if _anthropic is not None:
        try:
            # Anthropic SDK exposes .close() on AsyncAnthropic.
            close = getattr(_anthropic, "close", None)
            if close is not None and asyncio.iscoroutinefunction(close):
                await close()
        except Exception as e:
            log.warning("anthropic.close_failed", error=str(e))
        _anthropic = None
