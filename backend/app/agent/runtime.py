"""Per-run runtime context: emits trace events, tracks costs, talks to Langfuse."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Literal, cast

from backend.app.logging_setup import get_logger
from backend.app.schemas.events import (
    NodeFinishEvent,
    NodeStartEvent,
    ToolCallEvent,
    TraceEvent,
)
from backend.app.schemas.state import NodeRun, NodeStatus, ToolError
from backend.app.sse import EventBroker
from backend.app.store import RunStore

log = get_logger(__name__)


class RunContext:
    """Owned by the runner, passed into every node call."""

    def __init__(
        self,
        *,
        job_id: str,
        broker: EventBroker,
        store: RunStore,
        trace: Any,
    ) -> None:
        self.job_id = job_id
        self.broker = broker
        self.store = store
        self.trace = trace  # langfuse trace, or NoopTrace
        self._seq = 0
        self.total_cost_usd = 0.0
        # Accumulated per-node records + tool errors. The runner copies these
        # into the final ``AgentState`` before persisting, so the schema
        # fields ``node_runs`` and ``errors`` carry real data.
        self.node_runs: dict[str, NodeRun] = {}
        self.errors: list[ToolError] = []

    async def _emit(self, event: TraceEvent) -> None:
        self._seq += 1
        await self.store.append_event(self.job_id, self._seq, event)
        await self.broker.publish(event)

    @asynccontextmanager
    async def node(self, name: str, *, summary: str = "") -> AsyncIterator[NodeRecorder]:
        await self._emit(NodeStartEvent(job_id=self.job_id, node=name, input_summary=summary))
        started_at = datetime.now(UTC)
        rec = NodeRecorder(name=name)
        rec.started_at = started_at
        t0 = time.perf_counter()
        try:
            yield rec
        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            log.exception("node.failed", node=name, job_id=self.job_id)
            self.node_runs[name] = NodeRun(
                name=name,
                status=NodeStatus.FAILED,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                input_tokens=rec.input_tokens,
                output_tokens=rec.output_tokens,
                cost_usd=rec.cost_usd,
                error=ToolError(tool=name, message=str(e)[:300]),
                notes=rec.notes,
            )
            await self._emit(
                NodeFinishEvent(
                    job_id=self.job_id,
                    node=name,
                    status="failed",
                    duration_ms=duration_ms,
                    input_tokens=rec.input_tokens,
                    output_tokens=rec.output_tokens,
                    cost_usd=rec.cost_usd,
                    error_message=str(e)[:300],
                    notes=rec.notes,
                )
            )
            raise
        else:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            self.total_cost_usd += rec.cost_usd
            raw_status = rec.status.value if rec.status != NodeStatus.PENDING else "done"
            if raw_status not in ("done", "failed", "skipped"):
                raw_status = "done"
            status = cast(Literal["done", "failed", "skipped"], raw_status)
            self.node_runs[name] = NodeRun(
                name=name,
                status=NodeStatus(raw_status),
                started_at=started_at,
                finished_at=datetime.now(UTC),
                input_tokens=rec.input_tokens,
                output_tokens=rec.output_tokens,
                cost_usd=rec.cost_usd,
                error=rec.error,
                notes=rec.notes,
            )
            if rec.error is not None:
                self.errors.append(rec.error)
            await self._emit(
                NodeFinishEvent(
                    job_id=self.job_id,
                    node=name,
                    status=status,
                    duration_ms=duration_ms,
                    input_tokens=rec.input_tokens,
                    output_tokens=rec.output_tokens,
                    cost_usd=rec.cost_usd,
                    error_message=(rec.error.message if rec.error else None),
                    notes=rec.notes,
                )
            )

    async def tool_call(
        self,
        *,
        node: str,
        tool: str,
        target: str,
        success: bool,
        duration_ms: int,
        error_message: str | None = None,
    ) -> None:
        await self._emit(
            ToolCallEvent(
                job_id=self.job_id,
                node=node,
                tool=tool,
                target=target,
                success=success,
                duration_ms=duration_ms,
                error_message=error_message,
            )
        )


class NodeRecorder:
    """Mutable per-node bookkeeping. Nodes mutate this; ctx.node(...) reads it."""

    def __init__(self, *, name: str) -> None:
        self.name = name
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.notes = ""
        self.status: NodeStatus = NodeStatus.DONE
        self.error: ToolError | None = None
        self.started_at: datetime = datetime.now(UTC)

    def add_usage(self, *, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost_usd

    def mark_skipped(self, why: str) -> None:
        self.status = NodeStatus.SKIPPED
        self.notes = why

    def mark_failed(self, err: ToolError) -> None:
        self.status = NodeStatus.FAILED
        self.error = err
