"""Run the agent against the 3 sample companies and dump fixtures.

Outputs:
  examples/linear.json
  examples/faire.json
  examples/allbirds.json

Each file contains:
  {
    "id": "linear",
    "started_at": "...",
    "scorecard": {...},
    "events": [...]      # full timeline replay for the static demo
  }

Usage:
  python -m scripts.record_examples
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from backend.app.sse import EventBroker
from backend.app.store import RunStore
from backend.app.workers.runner import execute_run

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "examples"

SAMPLES: list[dict[str, str]] = [
    {
        "id": "linear",
        "company_url": "https://linear.app",
        "persona_id": "ae_series_b_saas",
    },
    {
        "id": "faire",
        "company_url": "https://faire.com",
        "persona_id": "revops_plg",
    },
    {
        "id": "allbirds",
        "company_url": "https://allbirds.com",
        "persona_id": "revops_plg",
    },
]


async def record(sample: dict[str, str]) -> None:
    from backend.app.personas import resolve_persona

    name, text = resolve_persona(sample["persona_id"], None)

    db_path = str(EXAMPLES / "_record.db")
    store = RunStore(db_path)
    await store.init()
    broker = EventBroker()

    print(f"\n=== {sample['id']} ({sample['company_url']}) ===")
    job_id = await execute_run(
        company_url=sample["company_url"],
        persona_name=name,
        persona_text=text,
        broker=broker,
        store=store,
    )
    run = await store.get_run(job_id)
    if run is None or not run.get("scorecard"):
        print(f"  FAILED: {run.get('error_message') if run else 'no run'}", file=sys.stderr)
        return
    events = await store.get_events(job_id)
    out: dict[str, Any] = {
        "id": sample["id"],
        "company_url": sample["company_url"],
        "persona_id": sample["persona_id"],
        "persona_name": name,
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
        "total_cost_usd": run["total_cost_usd"],
        "trace_url": run["trace_url"],
        "scorecard": run["scorecard"],
        "events": events,
    }
    EXAMPLES.mkdir(exist_ok=True)
    (EXAMPLES / f"{sample['id']}.json").write_text(json.dumps(out, indent=2))
    print(f"  wrote examples/{sample['id']}.json, score={run['scorecard']['icp_fit_score']}")


async def main() -> int:
    for s in SAMPLES:
        try:
            await record(s)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR for {s['id']}: {e}", file=sys.stderr)
    # Clean up the temp DB
    p = EXAMPLES / "_record.db"
    if p.exists():
        p.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
