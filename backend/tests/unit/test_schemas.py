"""Schema validation, proves the strict contracts behave as documented."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.scorecard import (
    Citation,
    Company,
    DecisionMaker,
    ICPClaim,
    ICPScorecard,
    NewsSignal,
    StackEntry,
)


def test_company_size_estimate_must_be_in_enum() -> None:
    with pytest.raises(ValidationError):
        Company(name="X", domain="x.com", industry="SaaS", size_estimate="huge")  # type: ignore[arg-type]


def test_icp_fit_score_bounds() -> None:
    with pytest.raises(ValidationError):
        ICPScorecard(
            company=Company(name="X", domain="x.com", industry="SaaS", size_estimate="51-200"),
            icp_fit_score=101,
            icp_reasoning=[ICPClaim(claim="ok claim text", confidence=0.5)],
            recommended_outreach_angle="Long enough recommendation here",
            estimated_research_cost_usd=0.0,
        )


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        Citation(
            url="https://x.com",  # type: ignore[arg-type]
            title="ok",
            extra_field="nope",  # type: ignore[call-arg]
        )


def test_decision_maker_linkedin_optional() -> None:
    dm = DecisionMaker(
        name="Jane Smith",
        title="VP Sales",
        relevance="Owns the buying decision",
        confidence=0.8,
    )
    assert dm.linkedin is None


def test_news_signal_round_trip() -> None:
    s = NewsSignal(
        headline="Acquired",
        url="https://example.com/news",  # type: ignore[arg-type]
        buyer_relevance="Signals revenue motion",
        confidence=0.7,
    )
    rt = NewsSignal.model_validate_json(s.model_dump_json())
    assert rt.confidence == s.confidence


def test_stack_entry_category_strict() -> None:
    with pytest.raises(ValidationError):
        StackEntry(category="bogus", tool="Foo", evidence="x", confidence=0.5)  # type: ignore[arg-type]
