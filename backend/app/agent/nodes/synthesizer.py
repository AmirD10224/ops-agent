"""SYNTHESIZER node. Sonnet 4.6 produces the ICP scorecard."""

from __future__ import annotations

import json
from typing import Any

from backend.app.agent.llm import call_structured
from backend.app.agent.prompts import load
from backend.app.agent.runtime import RunContext
from backend.app.config import get_settings
from backend.app.schemas.scorecard import ICPScorecard
from backend.app.schemas.state import AgentState

# Trim long fields before serializing, keeps prompt tokens predictable.
_MAX_PAGE_TEXT = 4_500
_MAX_PAGES = 4


def _build_inputs_payload(state: AgentState) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "persona": {
            "name": state.meta.persona_name,
            "text": state.meta.persona_text,
        },
        "company_url": state.meta.company_url,
    }
    # Surface degraded inputs so the synthesizer doesn't hallucinate a
    # confident scorecard from no actual evidence.
    degraded: list[str] = []
    if state.scrape and not state.scrape.pages:
        degraded.append(
            "scrape: zero pages reachable, do NOT produce confident company "
            "claims; lower confidence and surface a confidence_warning."
        )
    if state.news is None or not state.news.signals:
        degraded.append("news: no signals returned, recent_signals must be empty.")
    if state.people is None or not state.people.people:
        degraded.append("people: no candidates returned, decision_makers must be empty.")
    if state.stack is None or not state.stack.stack:
        degraded.append("stack: no signals, tech_stack must be empty or low-confidence.")
    if degraded:
        payload["degraded_inputs"] = degraded
    if state.scrape:
        payload["scrape"] = {
            "canonical_domain": state.scrape.canonical_domain,
            "detected_name": state.scrape.detected_name,
            "pages": [
                {
                    "url": str(p.url),
                    "title": p.title,
                    "text": p.text[:_MAX_PAGE_TEXT],
                }
                for p in state.scrape.pages[:_MAX_PAGES]
            ],
        }
    if state.news:
        payload["news"] = [s.model_dump(mode="json") for s in state.news.signals]
    if state.people:
        payload["people"] = [p.model_dump(mode="json") for p in state.people.people]
    if state.stack:
        payload["stack"] = [s.model_dump(mode="json") for s in state.stack.stack]
    if state.critique and state.critic_passes > 0:
        payload["prior_critique"] = {
            "issues": [i.model_dump() for i in state.critique.issues],
            "summary": state.critique.summary,
            "guidance": (
                "Address each high-severity issue. Lower confidence on under-supported claims."
            ),
        }
    return payload


async def run_synthesizer(state: AgentState, *, ctx: RunContext) -> dict[str, ICPScorecard]:
    settings = get_settings()
    payload = _build_inputs_payload(state)
    user = "INPUTS:\n" + json.dumps(payload, default=str, ensure_ascii=False)

    async with ctx.node(
        "synthesizer",
        summary=f"pass {state.critic_passes + 1}",
    ) as rec:
        result = await call_structured(
            model=settings.synthesizer_model,
            system=load("synthesizer"),
            user=user,
            schema=ICPScorecard,
            max_tokens=4000,
            temperature=0.3,
        )
        rec.add_usage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost_usd=result.usage.cost_usd,
        )
        rec.notes = f"score={result.parsed.icp_fit_score}"
    return {"scorecard": result.parsed}
