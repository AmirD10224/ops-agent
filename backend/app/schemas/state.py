"""LangGraph agent state, what flows between nodes."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.nodes import (
    CritiqueResult,
    NewsResult,
    PeopleResult,
    PlannerResult,
    ScrapeResult,
    StackResult,
)
from backend.app.schemas.scorecard import ICPScorecard, StrictModel


class NodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class ToolError(BaseModel):
    """Returned by tools instead of raising. Lets the agent reason about failure."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    message: str
    retryable: bool = False
    attempt: int = 1


class NodeRun(StrictModel):
    """Per-node execution record, what Langfuse and the SSE stream show."""

    name: str
    status: NodeStatus = NodeStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: ToolError | None = None
    notes: str = ""


class RunMeta(StrictModel):
    """Top-level run metadata."""

    job_id: str = Field(default_factory=lambda: uuid4().hex)
    company_url: str
    persona_name: str
    persona_text: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    total_cost_usd: float = 0.0
    trace_id: str | None = None
    trace_url: str | None = None


def _empty_node_runs() -> dict[str, NodeRun]:
    return {
        "planner": NodeRun(name="planner"),
        "scraper": NodeRun(name="scraper"),
        "news": NodeRun(name="news"),
        "people": NodeRun(name="people"),
        "stack": NodeRun(name="stack"),
        "synthesizer": NodeRun(name="synthesizer"),
        "critic": NodeRun(name="critic"),
    }


class AgentState(BaseModel):
    """The full LangGraph state. Mutable; nodes return partial updates."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    meta: RunMeta
    plan: PlannerResult | None = None
    scrape: ScrapeResult | None = None
    news: NewsResult | None = None
    people: PeopleResult | None = None
    stack: StackResult | None = None
    scorecard: ICPScorecard | None = None
    critique: CritiqueResult | None = None
    critic_passes: int = 0
    errors: list[ToolError] = Field(default_factory=list)
    node_runs: dict[str, NodeRun] = Field(default_factory=_empty_node_runs)
