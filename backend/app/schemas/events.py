"""SSE trace events, the live stream the UI consumes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NodeStartEvent(_Event):
    type: Literal["node_start"] = "node_start"
    node: str
    input_summary: str = ""


class NodeFinishEvent(_Event):
    type: Literal["node_finish"] = "node_finish"
    node: str
    status: Literal["done", "failed", "skipped"]
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error_message: str | None = None
    notes: str = ""


class ToolCallEvent(_Event):
    type: Literal["tool_call"] = "tool_call"
    node: str
    tool: str
    target: str
    success: bool
    duration_ms: int
    error_message: str | None = None


class RunFinishEvent(_Event):
    type: Literal["run_finish"] = "run_finish"
    status: Literal["done", "failed"]
    total_cost_usd: float
    total_duration_ms: int
    trace_url: str | None = None


TraceEvent = Annotated[
    NodeStartEvent | NodeFinishEvent | ToolCallEvent | RunFinishEvent,
    Field(discriminator="type"),
]
