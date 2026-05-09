"""Event broker pub/sub semantics."""

from __future__ import annotations

import asyncio

from backend.app.schemas.events import NodeStartEvent
from backend.app.sse import EventBroker


async def test_subscriber_receives_published_events() -> None:
    broker = EventBroker()
    received: list[NodeStartEvent] = []

    async def consume() -> None:
        async for evt in broker.subscribe("job1"):
            assert evt.type == "node_start"
            received.append(evt)  # type: ignore[arg-type]
            if len(received) == 2:
                await broker.close("job1")

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await broker.publish(NodeStartEvent(job_id="job1", node="planner"))
    await broker.publish(NodeStartEvent(job_id="job1", node="scraper"))
    await asyncio.wait_for(task, timeout=1.0)
    assert [e.node for e in received] == ["planner", "scraper"]


async def test_subscriber_to_already_closed_returns_empty() -> None:
    broker = EventBroker()
    await broker.close("done-job")
    seen: list[NodeStartEvent] = []
    async for evt in broker.subscribe("done-job"):
        seen.append(evt)  # type: ignore[arg-type]
    assert seen == []
