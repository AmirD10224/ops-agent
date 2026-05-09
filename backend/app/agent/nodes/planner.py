"""PLANNER node. Haiku 4.5 decomposes the run into subtasks."""

from __future__ import annotations

from backend.app.agent.llm import call_structured
from backend.app.agent.prompts import load
from backend.app.agent.runtime import RunContext
from backend.app.config import get_settings
from backend.app.schemas.nodes import PlannerResult
from backend.app.schemas.state import AgentState

PLANNER_USER_TEMPLATE = """\
Company URL: {company_url}

Buyer persona ({persona_name}):
{persona_text}
"""


async def run_planner(state: AgentState, *, ctx: RunContext) -> dict[str, PlannerResult]:
    settings = get_settings()
    async with ctx.node("planner", summary=f"plan for {state.meta.company_url}") as rec:
        result = await call_structured(
            model=settings.planner_model,
            system=load("planner"),
            user=PLANNER_USER_TEMPLATE.format(
                company_url=state.meta.company_url,
                persona_name=state.meta.persona_name,
                persona_text=state.meta.persona_text,
            ),
            schema=PlannerResult,
            max_tokens=800,
            temperature=0.0,
        )
        rec.add_usage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost_usd=result.usage.cost_usd,
        )
        rec.notes = f"{len(result.parsed.subtasks)} subtasks"
    return {"plan": result.parsed}
