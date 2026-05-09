"""SQLite-backed run store. Persists jobs, scorecards, and trace events."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from backend.app.config import get_settings
from backend.app.schemas.events import TraceEvent
from backend.app.schemas.scorecard import ICPScorecard
from backend.app.schemas.state import RunMeta

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    job_id        TEXT PRIMARY KEY,
    company_url   TEXT NOT NULL,
    persona_name  TEXT NOT NULL,
    persona_text  TEXT NOT NULL,
    status        TEXT NOT NULL,           -- queued | running | done | failed
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    total_cost_usd REAL NOT NULL DEFAULT 0,
    trace_url     TEXT,
    scorecard_json TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id    TEXT NOT NULL,
    seq       INTEGER NOT NULL,
    type      TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload   TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES runs(job_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_events_job_seq ON events (job_id, seq);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs (started_at DESC);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RunStore:
    def __init__(self, path: str | None = None) -> None:
        self._path = path or get_settings().sqlite_path
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        mode = get_settings().sqlite_journal_mode
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(f"PRAGMA journal_mode={mode};")
            await conn.execute("PRAGMA foreign_keys=ON;")
            conn.row_factory = aiosqlite.Row
            yield conn

    async def init(self) -> None:
        if self._initialized:
            return
        async with self._connect() as conn:
            await conn.executescript(_SCHEMA)
            await conn.commit()
        self._initialized = True

    async def create_run(self, meta: RunMeta) -> None:
        async with self._connect() as conn:
            await conn.execute(
                """
                INSERT INTO runs (job_id, company_url, persona_name, persona_text,
                                  status, started_at)
                VALUES (?, ?, ?, ?, 'queued', ?)
                """,
                (
                    meta.job_id,
                    meta.company_url,
                    meta.persona_name,
                    meta.persona_text,
                    meta.started_at.isoformat(),
                ),
            )
            await conn.commit()

    async def set_status(
        self,
        job_id: str,
        status: str,
        *,
        error: str | None = None,
        trace_url: str | None = None,
    ) -> None:
        async with self._connect() as conn:
            await conn.execute(
                """
                UPDATE runs
                   SET status = ?,
                       error_message = COALESCE(?, error_message),
                       trace_url = COALESCE(?, trace_url),
                       finished_at = CASE WHEN ? IN ('done','failed') THEN ? ELSE finished_at END
                 WHERE job_id = ?
                """,
                (status, error, trace_url, status, _now(), job_id),
            )
            await conn.commit()

    async def save_scorecard(
        self, job_id: str, card: ICPScorecard, *, total_cost_usd: float
    ) -> None:
        async with self._connect() as conn:
            await conn.execute(
                """
                UPDATE runs
                   SET scorecard_json = ?,
                       total_cost_usd = ?
                 WHERE job_id = ?
                """,
                (card.model_dump_json(), total_cost_usd, job_id),
            )
            await conn.commit()

    async def append_event(self, job_id: str, seq: int, event: TraceEvent) -> None:
        async with self._connect() as conn:
            await conn.execute(
                """
                INSERT INTO events (job_id, seq, type, timestamp, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    seq,
                    event.type,
                    event.timestamp.isoformat(),
                    event.model_dump_json(),
                ),
            )
            await conn.commit()

    async def get_run(self, job_id: str) -> dict[str, Any] | None:
        async with self._connect() as conn:
            cur = await conn.execute("SELECT * FROM runs WHERE job_id = ?", (job_id,))
            row = await cur.fetchone()
            if row is None:
                return None
            return _row_to_run(row)

    async def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        async with self._connect() as conn:
            cur = await conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
            return [_row_to_run(r) for r in rows]

    async def get_events(self, job_id: str) -> list[dict[str, Any]]:
        async with self._connect() as conn:
            cur = await conn.execute(
                "SELECT * FROM events WHERE job_id = ? ORDER BY seq ASC",
                (job_id,),
            )
            rows = await cur.fetchall()
            return [
                {
                    "seq": r["seq"],
                    "type": r["type"],
                    "timestamp": r["timestamp"],
                    "payload": json.loads(r["payload"]),
                }
                for r in rows
            ]


def _row_to_run(row: aiosqlite.Row) -> dict[str, Any]:
    sc = row["scorecard_json"]
    return {
        "job_id": row["job_id"],
        "company_url": row["company_url"],
        "persona_name": row["persona_name"],
        "persona_text": row["persona_text"],
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "total_cost_usd": row["total_cost_usd"],
        "trace_url": row["trace_url"],
        "error_message": row["error_message"],
        "scorecard": json.loads(sc) if sc else None,
    }


_store: RunStore | None = None


def get_store() -> RunStore:
    global _store
    if _store is None:
        _store = RunStore()
    return _store


def reset_store_for_tests(path: str) -> RunStore:
    """Used only by tests, replaces singleton with isolated path."""
    global _store
    if os.path.exists(path):
        os.remove(path)
    _store = RunStore(path)
    return _store
