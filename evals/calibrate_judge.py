"""Cohen's κ between human verdicts and the LLM-judge.

Usage:
  python -m evals.calibrate_judge --labels evals/human_labels.csv --scorecards examples/
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Literal

from evals.judge import judge_scorecard

Verdict = Literal["pass", "borderline", "fail"]
LABELS: tuple[Verdict, ...] = ("pass", "borderline", "fail")


def cohen_kappa(human: list[Verdict], judge: list[Verdict]) -> float:
    if len(human) != len(judge) or not human:
        raise ValueError("paired non-empty lists required")
    n = len(human)
    obs = sum(1 for h, j in zip(human, judge, strict=True) if h == j) / n
    h_counts = {l: human.count(l) / n for l in LABELS}
    j_counts = {l: judge.count(l) / n for l in LABELS}
    chance = sum(h_counts[l] * j_counts[l] for l in LABELS)
    if chance >= 1.0:  # degenerate
        return 1.0 if obs == 1.0 else 0.0
    return round((obs - chance) / (1 - chance), 4)


async def main_async(args: argparse.Namespace) -> int:
    pairs: list[tuple[Verdict, Verdict]] = []
    sc_dir = Path(args.scorecards)
    with open(args.labels) as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["id"]
            human = row["verdict"].strip().lower()
            if human not in LABELS:
                print(f"skip {sid}: bad human verdict {human!r}", file=sys.stderr)
                continue
            sc_path = sc_dir / f"{sid}.json"
            if not sc_path.exists():
                print(f"skip {sid}: no scorecard at {sc_path}", file=sys.stderr)
                continue
            data = json.loads(sc_path.read_text())
            scorecard = data.get("scorecard") if "scorecard" in data else data
            verdict = await judge_scorecard(scorecard)
            pairs.append((human, verdict.verdict))  # type: ignore[arg-type]
            print(f"{sid}: human={human}, judge={verdict.verdict}, overall={verdict.overall:.2f}")
    if not pairs:
        print("no usable rows", file=sys.stderr)
        return 2
    h, j = zip(*pairs, strict=True)
    k = cohen_kappa(list(h), list(j))
    print(f"\nCohen's κ = {k}  (n={len(pairs)})")
    if k < 0.7:
        print("Below target. Iterate the judge prompt.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--labels", required=True, help="CSV with columns id, verdict")
    p.add_argument("--scorecards", required=True, help="Directory of <id>.json files")
    return asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
