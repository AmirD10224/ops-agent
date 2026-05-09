"""Eval runner, executes the agent against the golden set, writes a report.

Modes:
  --offline   skip live agent runs; use scorecards from `examples/<id>.json`
              and only score them. CI uses this.
  --live      hit Anthropic + Tavily for real. Requires keys.
  --limit N   only run the first N examples.

Usage:
  python -m evals.run --offline
  python -m evals.run --live --limit 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from evals.judge import judge_scorecard
from evals.metrics import evaluate_scorecard

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "evals" / "golden_set.jsonl"
EXAMPLES = REPO / "examples"
RESULTS = REPO / "evals" / "results"


def load_golden() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in GOLDEN.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def offline_scorecard_for(example_id: str) -> dict[str, Any] | None:
    path = EXAMPLES / f"{example_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text()).get("scorecard")


async def live_scorecard_for(row: dict[str, Any]) -> dict[str, Any]:
    # Lazy import to keep --offline mode dep-light.
    from backend.app.personas import resolve_persona
    from backend.app.sse import EventBroker
    from backend.app.store import RunStore
    from backend.app.workers.runner import execute_run

    persona_name, persona_text = resolve_persona(row.get("persona_id"), None)
    broker = EventBroker()
    store = RunStore(str(RESULTS / "eval.db"))
    await store.init()
    job_id = await execute_run(
        company_url=row["company_url"],
        persona_name=persona_name,
        persona_text=persona_text,
        broker=broker,
        store=store,
    )
    run = await store.get_run(job_id)
    if not run or not run.get("scorecard"):
        raise RuntimeError(f"live run produced no scorecard for {row['id']}")
    return run["scorecard"]


async def evaluate_one(
    row: dict[str, Any], *, mode: str, judge: bool
) -> dict[str, Any]:
    expected = row["expected"]
    actual: dict[str, Any] | None = None
    started = time.perf_counter()
    error: str | None = None
    try:
        if mode == "offline":
            actual = offline_scorecard_for(row["id"])
            if actual is None:
                return {
                    "id": row["id"],
                    "skipped": True,
                    "reason": "no example fixture; populate examples/ to score",
                }
        else:
            actual = await live_scorecard_for(row)
    except Exception as e:  # noqa: BLE001
        error = str(e)[:500]

    duration_ms = int((time.perf_counter() - started) * 1000)
    if actual is None:
        return {"id": row["id"], "error": error or "no scorecard", "duration_ms": duration_ms}

    field_scores, agg = evaluate_scorecard(actual, expected)
    out: dict[str, Any] = {
        "id": row["id"],
        "duration_ms": duration_ms,
        "aggregate_score": agg,
        "field_scores": [
            {"name": s.name, "score": s.score, "detail": s.detail} for s in field_scores
        ],
    }
    if judge:
        verdict = await judge_scorecard(actual)
        out["judge"] = verdict.model_dump()
    return out


async def main_async(args: argparse.Namespace) -> int:
    rows = load_golden()
    if args.limit:
        rows = rows[: args.limit]
    RESULTS.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for row in rows:
        r = await evaluate_one(row, mode=args.mode, judge=args.judge)
        results.append(r)
        scored = "skipped" if r.get("skipped") else r.get("aggregate_score")
        print(f"  {row['id']:18s} → {scored}")

    scored_only = [r for r in results if "aggregate_score" in r]
    summary = {
        "mode": args.mode,
        "judge": args.judge,
        "n": len(rows),
        "scored": len(scored_only),
        "skipped": sum(1 for r in results if r.get("skipped")),
        "errored": sum(1 for r in results if "error" in r and not r.get("skipped")),
        "mean_aggregate": (
            round(sum(r["aggregate_score"] for r in scored_only) / max(1, len(scored_only)), 3)
            if scored_only
            else 0.0
        ),
        "results": results,
    }
    out = RESULTS / f"eval-{args.mode}-{int(time.time())}.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out}")
    print(f"Mean aggregate: {summary['mean_aggregate']}")
    return 0 if summary["errored"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--offline", dest="mode", action="store_const", const="offline")
    parser.add_argument("--live", dest="mode", action="store_const", const="live")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--judge", action="store_true")
    args = parser.parse_args()
    if args.mode == "live" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY required for --live", file=sys.stderr)
        return 2
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
