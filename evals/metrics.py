"""Field-wise metrics for the eval suite."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FieldScore:
    name: str
    score: float  # 0.0–1.0
    detail: str


def score_icp_fit(
    actual: int | None, expected: int, tolerance: int = 15
) -> FieldScore:
    if actual is None:
        return FieldScore("icp_fit_score", 0.0, "missing")
    diff = abs(actual - expected)
    score = max(0.0, 1.0 - (max(0, diff - tolerance) / 50))
    return FieldScore(
        "icp_fit_score",
        round(score, 3),
        f"actual={actual}, expected={expected}±{tolerance}, diff={diff}",
    )


def score_size_bucket(actual: str | None, expected: str | None) -> FieldScore:
    if expected is None:
        return FieldScore("size_estimate", 1.0, "no expectation")
    if actual is None:
        return FieldScore("size_estimate", 0.0, "missing")
    return FieldScore(
        "size_estimate",
        1.0 if actual == expected else 0.0,
        f"actual={actual}, expected={expected}",
    )


def score_industry(actual: str | None, expected: str | None) -> FieldScore:
    """Token-overlap score on lower-cased word sets."""
    if expected is None:
        return FieldScore("industry", 1.0, "no expectation")
    if actual is None:
        return FieldScore("industry", 0.0, "missing")
    a = {t for t in actual.lower().split() if len(t) > 2}
    e = {t for t in expected.lower().split() if len(t) > 2}
    if not e:
        return FieldScore("industry", 0.5, "empty expectation tokens")
    overlap = len(a & e) / len(e)
    return FieldScore(
        "industry", round(overlap, 3), f"actual={actual!r}, expected={expected!r}"
    )


def score_stack_overlap(
    actual_tools: list[str], must_include_any: list[str]
) -> FieldScore:
    if not must_include_any:
        return FieldScore("tech_stack", 1.0, "no expectation")
    a = {t.lower() for t in actual_tools}
    e = {t.lower() for t in must_include_any}
    hit = bool(a & e)
    return FieldScore(
        "tech_stack",
        1.0 if hit else 0.0,
        f"matches={(a & e) or 'none'}, expected_any_of={must_include_any}",
    )


def score_outreach_keywords(
    text: str | None, must_include_any: list[str]
) -> FieldScore:
    if not must_include_any:
        return FieldScore("recommended_outreach_angle", 1.0, "no expectation")
    if not text:
        return FieldScore("recommended_outreach_angle", 0.0, "missing")
    low = text.lower()
    hits = [k for k in must_include_any if k.lower() in low]
    score = 1.0 if hits else 0.0
    return FieldScore(
        "recommended_outreach_angle",
        score,
        f"keyword_hits={hits}, any_of={must_include_any}",
    )


def aggregate(scores: list[FieldScore]) -> float:
    if not scores:
        return 0.0
    return round(sum(s.score for s in scores) / len(scores), 3)


def evaluate_scorecard(
    actual: dict[str, Any], expected: dict[str, Any]
) -> tuple[list[FieldScore], float]:
    company = actual.get("company") or {}
    exp_company = expected.get("company") or {}
    scores: list[FieldScore] = [
        score_icp_fit(
            actual.get("icp_fit_score"),
            int(expected.get("icp_fit_score", 50)),
            int(expected.get("icp_fit_score_tolerance", 15)),
        ),
        score_size_bucket(company.get("size_estimate"), exp_company.get("size_estimate")),
        score_industry(company.get("industry"), exp_company.get("industry")),
        score_stack_overlap(
            [s.get("tool", "") for s in (actual.get("tech_stack") or [])],
            list(expected.get("tech_stack_must_include_any") or []),
        ),
        score_outreach_keywords(
            actual.get("recommended_outreach_angle"),
            list(expected.get("must_reference_in_outreach_any") or []),
        ),
    ]
    return scores, aggregate(scores)
