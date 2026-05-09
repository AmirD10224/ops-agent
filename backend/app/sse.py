"""SSE event broker, per-job pub/sub for trace streaming."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from backend.app.schemas.events import TraceEvent


class EventBroker:
    """In-memory broker. One queue per job_id; multiple subscribers fan-out per queue.

    Designed for single-process FastAPI / Modal-container deployment. For horizontal
    scale-out, swap the dict-of-queues for Redis Pub/Sub or NATS.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[TraceEvent | None]]] = defaultdict(list)
        self._closed: set[str] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: TraceEvent) -> None:
        async with self._lock:
            queues = list(self._subs.get(event.job_id, ()))
        for q in queues:
            await q.put(event)

    async def close(self, job_id: str) -> None:
        async with self._lock:
            self._closed.add(job_id)
            queues = list(self._subs.get(job_id, ()))
        for q in queues:
            await q.put(None)  # sentinel, tells subscribers to exit

    async def subscribe(self, job_id: str) -> AsyncIterator[TraceEvent]:
        q: asyncio.Queue[TraceEvent | None] = asyncio.Queue()
        async with self._lock:
            self._subs[job_id].append(q)
            already_closed = job_id in self._closed
        if already_closed:
            return
        try:
            while True:
                evt = await q.get()
                if evt is None:
                    return
                yield evt
        finally:
            async with self._lock:
                if q in self._subs.get(job_id, []):
                    self._subs[job_id].remove(q)


_broker: EventBroker | None = None


def get_broker() -> EventBroker:
    global _broker
    if _broker is None:
        _broker = EventBroker()
    return _broker
