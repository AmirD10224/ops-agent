"""End-to-end run with mocked Anthropic + Tavily + HTTP."""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from backend.app.clients import close_http
from backend.app.workers.runner import execute_run

pytestmark = pytest.mark.integration

TAVILY_URL = "https://api.tavily.com/search"


def _planner_response() -> str:
    return json.dumps(
        {
            "company_hypothesis": "B2B SaaS company",
            "persona_summary": "AE selling RevOps tools",
            "subtasks": [
                {"name": "scrape", "rationale": "fetch site"},
                {"name": "news", "rationale": "recent signals"},
                {"name": "people", "rationale": "decision makers"},
                {"name": "stack", "rationale": "tech fit"},
            ],
        }
    )


def _scorecard_response() -> str:
    return json.dumps(
        {
            "company": {
                "name": "Acme",
                "domain": "acme.com",
                "industry": "B2B SaaS",
                "size_estimate": "51-200",
                "description": "Workflow tooling for engineering teams.",
            },
            "icp_fit_score": 78,
            "icp_reasoning": [
                {
                    "claim": "Mid-market headcount aligns with the persona ICP",
                    "evidence": [
                        {
                            "url": "https://acme.com/",
                            "title": "Acme. Workflow tooling",
                            "snippet": "We build workflow tooling for engineering teams.",
                        }
                    ],
                    "confidence": 0.8,
                }
            ],
            "decision_makers": [],
            "tech_stack": [
                {
                    "category": "analytics",
                    "tool": "Segment",
                    "evidence": "Detected segment.com script",
                    "confidence": 0.8,
                }
            ],
            "recent_signals": [
                {
                    "date": "2026-02-01",
                    "headline": "Acme raises $30M",
                    "url": "https://news.example/acme",
                    "buyer_relevance": "Recent funding correlates with budget availability.",
                    "confidence": 0.8,
                }
            ],
            "recommended_outreach_angle": (
                "Hi, saw Acme's Series B and your Segment integration. "
                "Two specific things we could solve given the ICP we usually serve."
            ),
            "confidence_warnings": [],
            "estimated_research_cost_usd": 0.0,
        }
    )


def _critic_response(needs_retry: bool = False, conf: float = 0.85) -> str:
    return json.dumps(
        {
            "overall_confidence": conf,
            "needs_retry": needs_retry,
            "issues": [
                {
                    "field": "icp_reasoning[0]",
                    "issue": "thin evidence, raise confidence only on corroboration",
                    "severity": "high" if needs_retry else "low",
                }
            ]
            if needs_retry
            else [],
            "summary": "Re-run synthesizer." if needs_retry else "Looks good.",
        }
    )


async def test_end_to_end_run_produces_scorecard(
    fake_anthropic,  # type: ignore[no-untyped-def]
    broker,
    store,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await close_http()
    # Order: planner → synthesizer → critic
    fake_anthropic.queue(_planner_response())
    fake_anthropic.queue(_scorecard_response())
    fake_anthropic.queue(_critic_response())

    # Replace the global store + broker with the per-test ones.
    from backend.app import sse
    from backend.app import store as store_mod

    monkeypatch.setattr(sse, "_broker", broker)
    monkeypatch.setattr(store_mod, "_store", store)

    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.com/").mock(
            return_value=Response(
                200,
                text=(
                    "<html><head><title>Acme, workflow</title></head>"
                    "<body><script src='https://cdn.segment.com/x.js'></script>"
                    "Acme builds workflow tooling.</body></html>"
                ),
                headers={"server": "cloudflare"},
            )
        )
        router.get(url__regex=r"^https://acme\.com/.+").mock(return_value=Response(404, text=""))
        router.post(TAVILY_URL).mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://news.example/acme",
                            "title": "Acme raises $30M",
                            "content": "Series B funding from XYZ Ventures.",
                            "score": 0.85,
                            "published_date": "2026-02-01",
                        }
                    ]
                },
            )
        )

        job_id = await execute_run(
            company_url="https://acme.com",
            persona_name="AE. Series B SaaS",
            persona_text="AE persona text long enough.",
            broker=broker,
            store=store,
        )

    run = await store.get_run(job_id)
    assert run is not None
    assert run["status"] == "done", run["error_message"]
    assert run["scorecard"]["icp_fit_score"] == 78
    assert run["scorecard"]["company"]["name"] == "Acme"
    # Cost is non-zero because of the FakeAnthropic token counts.
    assert run["total_cost_usd"] > 0
    # Events were persisted.
    events = await store.get_events(job_id)
    types = {e["type"] for e in events}
    assert {"node_start", "node_finish", "run_finish"}.issubset(types)
    await close_http()


async def test_critic_retry_loop_runs_synthesizer_twice_then_terminates(
    fake_anthropic,  # type: ignore[no-untyped-def]
    broker,
    store,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The critic returns ``needs_retry: True`` once; the graph loops back to
    the synthesizer; the second critic pass terminates. We assert exactly two
    synthesizer invocations and a final ``done`` status, the headline
    differentiator of the agent (the critic-driven retry loop) is exercised
    end-to-end here.
    """
    await close_http()
    fake_anthropic.queue(_planner_response())  # planner
    fake_anthropic.queue(_scorecard_response())  # synthesizer pass 1
    fake_anthropic.queue(_critic_response(needs_retry=True, conf=0.4))  # critic 1
    fake_anthropic.queue(_scorecard_response())  # synthesizer pass 2
    fake_anthropic.queue(_critic_response(needs_retry=False, conf=0.9))  # critic 2

    from backend.app import sse
    from backend.app import store as store_mod

    monkeypatch.setattr(sse, "_broker", broker)
    monkeypatch.setattr(store_mod, "_store", store)

    with respx.mock(assert_all_called=False) as router:
        router.get("https://acme.com/").mock(
            return_value=Response(
                200,
                text="<html><head><title>Acme</title></head><body>x</body></html>",
                headers={"server": "cloudflare"},
            )
        )
        router.get(url__regex=r"^https://acme\.com/.+").mock(return_value=Response(404, text=""))
        router.post(TAVILY_URL).mock(return_value=Response(200, json={"results": []}))

        job_id = await execute_run(
            company_url="https://acme.com",
            persona_name="AE. Series B SaaS",
            persona_text="AE persona text long enough to satisfy validation.",
            broker=broker,
            store=store,
        )

    run = await store.get_run(job_id)
    assert run is not None
    assert run["status"] == "done", run["error_message"]

    events = await store.get_events(job_id)
    synth_finishes = [
        e for e in events if e["type"] == "node_finish" and e["payload"]["node"] == "synthesizer"
    ]
    critic_finishes = [
        e for e in events if e["type"] == "node_finish" and e["payload"]["node"] == "critic"
    ]
    assert len(synth_finishes) == 2, "synthesizer must run twice when critic asks for retry"
    assert len(critic_finishes) == 2, "critic must run on each synthesizer pass"
    await close_http()
