"""FastAPI app. POST /research, SSE stream, result/list endpoints."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sse_starlette.sse import EventSourceResponse

from backend.app.clients import aclose_all
from backend.app.config import get_settings
from backend.app.logging_setup import configure_logging, get_logger
from backend.app.personas import list_personas, resolve_persona
from backend.app.sse import EventBroker, get_broker
from backend.app.store import RunStore, get_store
from backend.app.workers.runner import execute_run

log = get_logger(__name__)

# Hold strong refs to background research tasks. Plain ``asyncio.create_task``
# loses its only reference once the awaitable is fired, leaving the loop free
# to garbage-collect mid-run. We also use this set to cancel in-flight runs
# during lifespan shutdown.
_BACKGROUND_TASKS: set[asyncio.Task[str]] = set()


# ---------- Lifecycle ------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    store = get_store()
    await store.init()
    log.info("app.started", env=get_settings().app_env)
    try:
        yield
    finally:
        # Cancel anything still running so we mark the rows as failed
        # rather than leave them pinned to ``status='running'`` forever.
        if _BACKGROUND_TASKS:
            log.info("app.shutdown.cancel_tasks", n=len(_BACKGROUND_TASKS))
            for task in list(_BACKGROUND_TASKS):
                task.cancel()
            await asyncio.gather(*_BACKGROUND_TASKS, return_exceptions=True)
            _BACKGROUND_TASKS.clear()
        # Mark any orphaned ``running`` rows from previous restarts as failed.
        try:
            for row in await store.list_runs(limit=200):
                if row["status"] == "running":
                    await store.set_status(row["job_id"], "failed", error="server shutdown")
        except Exception as e:
            log.warning("app.shutdown.cleanup_failed", error=str(e))
        await aclose_all()
        log.info("app.stopped")


app = FastAPI(
    title="OpsAgent",
    version="0.1.0",
    description="Multi-step B2B sales research agent with full observability.",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex_or_none,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------- Request/response models ---------------------------------------


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_url: str = Field(min_length=3, max_length=600)
    persona_id: str | None = None
    persona_text: str | None = Field(default=None, max_length=4000)

    @field_validator("company_url")
    @classmethod
    def _normalize_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("company_url must not be empty")
        if "://" not in v:
            v = f"https://{v}"
        return v


class ResearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    stream_url: str
    result_url: str


# ---------- Dependencies ---------------------------------------------------


def _broker() -> EventBroker:
    return get_broker()


def _store() -> RunStore:
    return get_store()


# ---------- Routes ---------------------------------------------------------


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.get("/personas")
async def get_personas() -> dict[str, Any]:
    return {"personas": [p.model_dump() for p in list_personas()]}


@app.post(
    "/research",
    response_model=ResearchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_research(
    body: ResearchRequest,
    broker: EventBroker = Depends(_broker),
    store: RunStore = Depends(_store),
) -> ResearchResponse:
    try:
        persona_name, persona_text = resolve_persona(body.persona_id, body.persona_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    job_id = uuid4().hex
    task = asyncio.create_task(
        execute_run(
            company_url=body.company_url,
            persona_name=persona_name,
            persona_text=persona_text,
            job_id=job_id,
            broker=broker,
            store=store,
        ),
        name=f"research-{job_id}",
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    log.info("research.queued", job_id=job_id, url=body.company_url)
    return ResearchResponse(
        job_id=job_id,
        stream_url=f"/research/{job_id}/stream",
        result_url=f"/research/{job_id}",
    )


@app.get("/research/{job_id}")
async def get_research(
    job_id: str,
    store: RunStore = Depends(_store),
) -> JSONResponse:
    run = await store.get_run(job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JSONResponse(run)


@app.get("/research/{job_id}/events")
async def get_research_events(
    job_id: str,
    store: RunStore = Depends(_store),
) -> dict[str, Any]:
    """Replay all stored events for a finished run."""
    run = await store.get_run(job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="job not found")
    events = await store.get_events(job_id)
    return {"job_id": job_id, "status": run["status"], "events": events}


@app.get("/research/{job_id}/stream")
async def stream_research(
    job_id: str,
    broker: EventBroker = Depends(_broker),
    store: RunStore = Depends(_store),
) -> EventSourceResponse:
    """SSE stream, replays past events then tails live ones until run finishes."""
    run = await store.get_run(job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def gen() -> AsyncIterator[dict[str, Any]]:
        # 1. Replay anything already persisted (so reconnects work).
        replayed = await store.get_events(job_id)
        last_seq = 0
        for evt in replayed:
            last_seq = max(last_seq, int(evt["seq"]))
            yield {
                "event": evt["type"],
                "data": json.dumps(evt["payload"]),
                "id": str(evt["seq"]),
            }
        # 2. If already terminal, stop here.
        latest = await store.get_run(job_id)
        if latest and latest["status"] in {"done", "failed"}:
            yield {"event": "close", "data": json.dumps({"reason": latest["status"]})}
            return
        # 3. Top-up: any events the agent emitted between (1) and (3) are
        #    already in SQLite but won't appear in the live broker tail
        #    (subscribers only see events emitted *after* attach). Re-fetch
        #    by ``seq`` and replay them before tailing.
        catchup = [e for e in await store.get_events(job_id) if int(e["seq"]) > last_seq]
        for evt in catchup:
            last_seq = max(last_seq, int(evt["seq"]))
            yield {
                "event": evt["type"],
                "data": json.dumps(evt["payload"]),
                "id": str(evt["seq"]),
            }
        # 4. If terminal now, stop.
        latest = await store.get_run(job_id)
        if latest and latest["status"] in {"done", "failed"}:
            yield {"event": "close", "data": json.dumps({"reason": latest["status"]})}
            return
        # 5. Otherwise tail live events.
        async for live in broker.subscribe(job_id):
            yield {
                "event": live.type,
                "data": live.model_dump_json(),
            }
            if live.type == "run_finish":
                return

    return EventSourceResponse(gen())


@app.get("/traces")
async def list_traces(
    limit: int = 50,
    store: RunStore = Depends(_store),
) -> dict[str, Any]:
    runs = await store.list_runs(limit=min(max(limit, 1), 200))
    return {
        "runs": [
            {
                "job_id": r["job_id"],
                "company_url": r["company_url"],
                "persona_name": r["persona_name"],
                "status": r["status"],
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
                "total_cost_usd": r["total_cost_usd"],
                "trace_url": r["trace_url"],
                "icp_fit_score": (r.get("scorecard") or {}).get("icp_fit_score"),
            }
            for r in runs
        ]
    }
