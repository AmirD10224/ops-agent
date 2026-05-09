"""Langfuse wrapper, gracefully no-ops if keys aren't configured."""

from __future__ import annotations

from typing import Any

from backend.app.config import get_settings
from backend.app.logging_setup import get_logger

log = get_logger(__name__)


class _NoopSpan:
    def __init__(self, **_: Any) -> None: ...
    def end(self, **_: Any) -> None: ...
    def update(self, **_: Any) -> None: ...
    def generation(self, **kwargs: Any) -> _NoopSpan:
        return _NoopSpan()

    def span(self, **kwargs: Any) -> _NoopSpan:
        return _NoopSpan()


class _NoopTrace:
    id: str = ""

    def span(self, **_: Any) -> _NoopSpan:
        return _NoopSpan()

    def generation(self, **_: Any) -> _NoopSpan:
        return _NoopSpan()

    def update(self, **_: Any) -> None: ...

    def get_trace_url(self) -> str | None:
        return None


class TracingClient:
    """Thin facade over the Langfuse SDK.

    The agent code only uses .start_run/.start_span/.start_generation,
    so when Langfuse isn't configured we hand out no-op stand-ins.
    """

    def __init__(self) -> None:
        self._client: Any | None = None
        settings = get_settings()
        if not settings.langfuse_enabled:
            log.info("langfuse.disabled", reason="missing_keys")
            return
        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=settings.langfuse_public_key.get_secret_value(),
                secret_key=settings.langfuse_secret_key.get_secret_value(),
                host=settings.langfuse_host,
            )
            log.info("langfuse.enabled", host=settings.langfuse_host)
        except Exception as e:
            log.warning("langfuse.init_failed", error=str(e))
            self._client = None

    def start_run(self, *, job_id: str, company_url: str, persona: str) -> _NoopTrace | Any:
        if self._client is None:
            return _NoopTrace()
        try:
            return self._client.trace(
                name="ops_agent.run",
                id=job_id,
                input={"company_url": company_url, "persona": persona},
                tags=["ops-agent"],
            )
        except Exception as e:
            log.warning("langfuse.trace_failed", error=str(e))
            return _NoopTrace()

    def trace_url(self, trace: Any) -> str | None:
        try:
            url = trace.get_trace_url()
        except Exception:
            return None
        return url if isinstance(url, str) else None

    def flush(self) -> None:
        if self._client is None:
            return
        try:
            self._client.flush()
        except Exception as e:
            log.warning("langfuse.flush_failed", error=str(e))


_singleton: TracingClient | None = None


def get_tracer() -> TracingClient:
    global _singleton
    if _singleton is None:
        _singleton = TracingClient()
    return _singleton
