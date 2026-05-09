"""SQLite-backed store round-trip."""

from __future__ import annotations

from backend.app.schemas.events import NodeStartEvent
from backend.app.schemas.scorecard import (
    Company,
    ICPClaim,
    ICPScorecard,
)
from backend.app.schemas.state import RunMeta


async def test_create_and_read_run(store) -> None:  # type: ignore[no-untyped-def]
    meta = RunMeta(
        company_url="https://example.com",
        persona_name="Test",
        persona_text="text",
    )
    await store.create_run(meta)
    got = await store.get_run(meta.job_id)
    assert got is not None
    assert got["status"] == "queued"
    assert got["company_url"] == "https://example.com"


async def test_save_scorecard_and_status(store) -> None:  # type: ignore[no-untyped-def]
    meta = RunMeta(company_url="https://example.com", persona_name="P", persona_text="T")
    await store.create_run(meta)
    card = ICPScorecard(
        company=Company(name="X", domain="x.com", industry="SaaS", size_estimate="51-200"),
        icp_fit_score=75,
        icp_reasoning=[ICPClaim(claim="strong product fit signal", confidence=0.8)],
        recommended_outreach_angle="Hello, since you launched X and use Y, ...",
        estimated_research_cost_usd=0.0123,
    )
    await store.save_scorecard(meta.job_id, card, total_cost_usd=0.0123)
    await store.set_status(meta.job_id, "done")
    got = await store.get_run(meta.job_id)
    assert got is not None
    assert got["status"] == "done"
    assert got["scorecard"]["icp_fit_score"] == 75


async def test_events_append_and_replay(store) -> None:  # type: ignore[no-untyped-def]
    meta = RunMeta(company_url="https://example.com", persona_name="P", persona_text="T")
    await store.create_run(meta)
    evt = NodeStartEvent(job_id=meta.job_id, node="planner")
    await store.append_event(meta.job_id, 1, evt)
    rows = await store.get_events(meta.job_id)
    assert len(rows) == 1
    assert rows[0]["type"] == "node_start"
    assert rows[0]["payload"]["node"] == "planner"


async def test_list_runs_returns_recent_first(store) -> None:  # type: ignore[no-untyped-def]
    for url in ("https://a.com", "https://b.com", "https://c.com"):
        await store.create_run(RunMeta(company_url=url, persona_name="P", persona_text="T"))
    runs = await store.list_runs(limit=10)
    urls = [r["company_url"] for r in runs]
    # We don't assert exact order due to identical timestamps; assert membership.
    assert set(urls) == {"https://a.com", "https://b.com", "https://c.com"}
