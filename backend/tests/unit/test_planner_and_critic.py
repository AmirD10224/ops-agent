"""Planner and Critic nodes, driven by FakeAnthropic."""

from __future__ import annotations

import json

from backend.app.agent.nodes.critic import run_critic
from backend.app.agent.nodes.planner import run_planner
from backend.app.agent.runtime import RunContext
from backend.app.schemas.scorecard import (
    Citation,
    Company,
    ICPClaim,
    ICPScorecard,
)
from backend.app.schemas.state import AgentState, RunMeta


def _fresh_state() -> AgentState:
    return AgentState(
        meta=RunMeta(
            company_url="https://acme.com",
            persona_name="AE",
            persona_text="text",
        )
    )


async def test_planner_parses_subtasks(fake_anthropic, broker, store) -> None:  # type: ignore[no-untyped-def]
    state = _fresh_state()
    await store.create_run(state.meta)
    ctx = RunContext(job_id=state.meta.job_id, broker=broker, store=store, trace=object())
    fake_anthropic.queue(
        json.dumps(
            {
                "company_hypothesis": "B2B SaaS",
                "persona_summary": "AE Series B",
                "subtasks": [
                    {"name": "scrape", "rationale": "homepage useful"},
                    {"name": "news", "rationale": "recent funding"},
                    {"name": "people", "rationale": "buying committee"},
                    {"name": "stack", "rationale": "tech fit"},
                ],
            }
        )
    )
    res = await run_planner(state, ctx=ctx)
    assert len(res["plan"].subtasks) == 4


async def test_critic_caps_retries(fake_anthropic, broker, store) -> None:  # type: ignore[no-untyped-def]
    state = _fresh_state()
    state.scorecard = ICPScorecard(
        company=Company(name="X", domain="x.com", industry="SaaS", size_estimate="51-200"),
        icp_fit_score=80,
        icp_reasoning=[
            ICPClaim(
                claim="Strong product fit",
                evidence=[Citation(url="https://x.com", title="Home", snippet="...")],  # type: ignore[arg-type]
                confidence=0.85,
            )
        ],
        recommended_outreach_angle="Long enough recommendation referencing two findings.",
        estimated_research_cost_usd=0.0,
    )
    state.critic_passes = 1  # already at the configured cap (default max=1)
    await store.create_run(state.meta)
    ctx = RunContext(job_id=state.meta.job_id, broker=broker, store=store, trace=object())
    fake_anthropic.queue(
        json.dumps(
            {
                "overall_confidence": 0.4,
                "needs_retry": True,
                "issues": [
                    {"field": "icp_reasoning[0]", "issue": "low evidence", "severity": "high"}
                ],
                "summary": "needs more evidence",
            }
        )
    )
    res = await run_critic(state, ctx=ctx)
    # Retry forced to false because we're already at max.
    assert res["critique"].needs_retry is False
