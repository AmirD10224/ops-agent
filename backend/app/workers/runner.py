"""Orchestrates a single research run end-to-end."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from backend.app.agent.graph import build_graph
from backend.app.agent.runtime import RunContext
from backend.app.logging_setup import get_logger
from backend.app.schemas.events import RunFinishEvent
from backend.app.schemas.state import AgentState, RunMeta
from backend.app.sse import EventBroker, get_broker
from backend.app.store import RunStore, get_store
from backend.app.tracing import get_tracer

log = get_logger(__name__)


async def execute_run(
    *,
    company_url: str,
    persona_name: str,
    persona_text: str,
    job_id: str | None = None,
    broker: EventBroker | None = None,
    store: RunStore | None = None,
) -> str:
    """Run the agent end-to-end. Returns the job_id.

    This is `await`-able and intended to be wrapped in `asyncio.create_task` by
    the FastAPI handler so the HTTP response can return immediately while the
    job continues in-process.
    """
    broker = broker or get_broker()
    store = store or get_store()
    tracer = get_tracer()

    if job_id:
        meta = RunMeta(
            job_id=job_id,
            company_url=company_url,
            persona_name=persona_name,
            persona_text=persona_text,
        )
    else:
        meta = RunMeta(
            company_url=company_url,
            persona_name=persona_name,
            persona_text=persona_text,
        )
    state = AgentState(meta=meta)

    await store.create_run(meta)
    await store.set_status(meta.job_id, "running")

    trace = tracer.start_run(
        job_id=meta.job_id,
        company_url=company_url,
        persona=persona_name,
    )
    trace_url = tracer.trace_url(trace)
    if trace_url:
        await store.set_status(meta.job_id, "running", trace_url=trace_url)

    ctx = RunContext(job_id=meta.job_id, broker=broker, store=store, trace=trace)
    graph = build_graph()

    t0 = time.perf_counter()
    status: str = "done"
    error_msg: str | None = None
    cancelled = False
    try:
        final_state_dict: dict[str, Any] = await graph.ainvoke(
            state.model_dump(),
            config={"configurable": {"ctx": ctx}, "recursion_limit": 25},
        )
        final_state = AgentState.model_validate(final_state_dict)
        # Wire the runtime-collected per-node records and tool errors into
        # the final state so ``state.node_runs`` / ``state.errors`` reflect
        # what actually happened during the run.
        final_state.node_runs = {**final_state.node_runs, **ctx.node_runs}
        final_state.errors = [*final_state.errors, *ctx.errors]
        if final_state.scorecard is None:
            raise RuntimeError("graph completed without producing a scorecard")

        # Stamp trace_url and confidence warnings into the final scorecard.
        warnings: list[str] = list(final_state.scorecard.confidence_warnings)
        if final_state.critique:
            warnings.extend(
                f"[{i.severity}] {i.field}: {i.issue}"
                for i in final_state.critique.issues
                if i.severity in ("medium", "high")
            )
        scorecard = final_state.scorecard.model_copy(
            update={
                "trace_url": trace_url,
                "estimated_research_cost_usd": round(ctx.total_cost_usd, 6),
                "confidence_warnings": warnings[:10],
            }
        )
        await store.save_scorecard(meta.job_id, scorecard, total_cost_usd=ctx.total_cost_usd)
    except asyncio.CancelledError:
        status = "failed"
        error_msg = "cancelled"
        cancelled = True
        log.info("run.cancelled", job_id=meta.job_id)
    except Exception as e:
        status = "failed"
        error_msg = str(e)[:500]
        log.exception("run.failed", job_id=meta.job_id)
    finally:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        await ctx._emit(
            RunFinishEvent(
                job_id=meta.job_id,
                status=status,  # type: ignore[arg-type]
                total_cost_usd=round(ctx.total_cost_usd, 6),
                total_duration_ms=duration_ms,
                trace_url=trace_url,
            )
        )
        await store.set_status(meta.job_id, status, error=error_msg, trace_url=trace_url)
        await broker.close(meta.job_id)
        tracer.flush()
    if cancelled:
        # Re-raise so the cancelling caller observes the cancellation,
        # but only AFTER persisting the failed row + closing the broker.
        raise asyncio.CancelledError
    return meta.job_id
