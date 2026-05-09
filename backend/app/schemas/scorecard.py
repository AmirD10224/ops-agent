"""ICP scorecard, the final structured output the agent produces."""

from __future__ import annotations

from datetime import date as DateT
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StrictModel(BaseModel):
    """Base for all schemas, strict, no extras, frozen-ish."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# Confidence scores are 0-1 floats. Keep this alias for self-documenting fields.
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class Citation(StrictModel):
    """A single source citation backing a claim."""

    url: HttpUrl
    title: str = Field(min_length=1, max_length=300)
    snippet: str = Field(default="", max_length=600)


class Company(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=253)
    industry: str = Field(min_length=1, max_length=120)
    size_estimate: Literal[
        "1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001+", "unknown"
    ]
    description: str = Field(default="", max_length=600)


class ICPClaim(StrictModel):
    claim: str = Field(min_length=5, max_length=400)
    evidence: list[Citation] = Field(default_factory=list, max_length=5)
    confidence: Confidence


class DecisionMaker(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=160)
    linkedin: HttpUrl | None = None
    relevance: str = Field(min_length=3, max_length=300)
    confidence: Confidence


class StackEntry(StrictModel):
    category: Literal[
        "analytics",
        "auth",
        "cdn",
        "cms",
        "crm",
        "database",
        "ecommerce",
        "hosting",
        "language",
        "marketing",
        "monitoring",
        "payments",
        "support",
        "framework",
        "other",
    ]
    tool: str = Field(min_length=1, max_length=80)
    evidence: str = Field(min_length=1, max_length=300)
    confidence: Confidence


class NewsSignal(StrictModel):
    date: DateT | None = None
    headline: str = Field(min_length=1, max_length=300)
    url: HttpUrl
    buyer_relevance: str = Field(min_length=3, max_length=400)
    confidence: Confidence


class ICPScorecard(StrictModel):
    """The end-to-end scorecard, the contract between agent and UI."""

    company: Company
    icp_fit_score: int = Field(ge=0, le=100)
    icp_reasoning: list[ICPClaim] = Field(min_length=1, max_length=10)
    decision_makers: list[DecisionMaker] = Field(default_factory=list, max_length=10)
    tech_stack: list[StackEntry] = Field(default_factory=list, max_length=20)
    recent_signals: list[NewsSignal] = Field(default_factory=list, max_length=10)
    recommended_outreach_angle: str = Field(min_length=20, max_length=1500)
    confidence_warnings: list[str] = Field(default_factory=list, max_length=10)
    estimated_research_cost_usd: float = Field(ge=0)
    trace_url: HttpUrl | None = None
