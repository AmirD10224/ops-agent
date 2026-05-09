"""CRITIC node. Sonnet 4.6 reviews the scorecard, decides retry."""

from __future__ import annotations

import json

from backend.app.agent.llm import call_structured
from backend.app.agent.prompts import load
from backend.app.agent.runtime import RunContext
from backend.app.config import get_settings
from backend.app.schemas.nodes import CritiqueResult
from backend.app.schemas.state import AgentState


def _allowed_urls_from_state(state: AgentState) -> list[str]:
    urls: set[str] = set()
    if state.scrape:
        urls.update(str(p.url) for p in state.scrape.pages)
    if state.news:
        urls.update(str(s.url) for s in state.news.signals)
    if state.people:
        for p in state.people.people:
            if p.linkedin:
                urls.add(str(p.linkedin))
    return sorted(urls)


async def run_critic(state: AgentState, *, ctx: RunContext) -> dict[str, CritiqueResult]:
    settings = get_settings()
    if state.scorecard is None:
        raise RuntimeError("critic invoked without a scorecard in state")

    user_payload = {
        "scorecard": state.scorecard.model_dump(mode="json"),
        "allowed_evidence_urls": _allowed_urls_from_state(state),
        "persona": {
            "name": state.meta.persona_name,
            "text": state.meta.persona_text,
        },
        "confidence_threshold": settings.confidence_threshold,
    }
    placeholder = "{{ confidence_threshold }}"
    raw = load("critic")
    if placeholder not in raw:  # pragma: no cover, guard against silent prompt drift
        raise RuntimeError(
            f"critic prompt is missing the {placeholder!r} placeholder; "
            "edit prompts/critic.v1.md or bump PROMPT_VERSIONS in prompts/__init__.py"
        )
    system = raw.replace(placeholder, f"{settings.confidence_threshold:.2f}")

    async with ctx.node("critic", summary="quality review") as rec:
        result = await call_structured(
            model=settings.critic_model,
            system=system,
            user="INPUTS:\n" + json.dumps(user_payload, default=str, ensure_ascii=False),
            schema=CritiqueResult,
            max_tokens=1500,
            temperature=0.0,
        )
        rec.add_usage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost_usd=result.usage.cost_usd,
        )
        retry_decision = (
            result.parsed.needs_retry and state.critic_passes < settings.max_critic_retries
        )
        rec.notes = (
            f"conf={result.parsed.overall_confidence:.2f}, "
            f"retry={retry_decision}, issues={len(result.parsed.issues)}"
        )

    # Force needs_retry to false if we've already hit the cap, saves a retry the
    # graph couldn't honor anyway.
    final = result.parsed
    if state.critic_passes >= settings.max_critic_retries:
        final = final.model_copy(update={"needs_retry": False})
    return {"critique": final}
