"""LLM-judge for reasoning quality.

We use a separate model invocation that grades the SYNTHESIZER's reasoning
on faithfulness (do citations actually support claims?) and specificity
(is the outreach concrete enough to send?). The judge is calibrated against
human labels, see judge_calibration.md.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.agent.llm import call_structured

JUDGE_MODEL = "claude-sonnet-4-6"


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faithfulness: float = Field(ge=0.0, le=1.0)
    specificity: float = Field(ge=0.0, le=1.0)
    overall: float = Field(ge=0.0, le=1.0)
    verdict: Literal["pass", "borderline", "fail"]
    rationale: str = Field(min_length=10, max_length=600)


_JUDGE_SYSTEM = """\
You are an evaluation judge for a B2B sales research agent. You will receive a
scorecard the agent produced. Score it on:

1. **faithfulness** [0.0–1.0]: Do every `claim` and `recent_signals` entry have
   evidence that genuinely supports them? (Random-feeling URLs, vague snippets,
   citations that don't relate → low score.)
2. **specificity** [0.0–1.0]: Is `recommended_outreach_angle` concrete (named
   tools, dated events, specific roles) rather than generic ("we help companies
   like yours")?

Then set:
- `overall` = mean of the two
- `verdict`: "pass" if overall ≥ 0.75, "borderline" if 0.5–0.75, else "fail"
- `rationale`: one paragraph explaining the score

Return JSON only.
"""


async def judge_scorecard(scorecard: dict[str, Any]) -> JudgeVerdict:
    user = "SCORECARD:\n" + json.dumps(scorecard, default=str, ensure_ascii=False)
    res = await call_structured(
        model=JUDGE_MODEL,
        system=_JUDGE_SYSTEM,
        user=user,
        schema=JudgeVerdict,
        max_tokens=800,
        temperature=0.0,
    )
    return res.parsed
