"""Per-node input/output models, strict typing for every transition."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from backend.app.schemas.scorecard import (
    DecisionMaker,
    NewsSignal,
    StackEntry,
    StrictModel,
)


class PlannerSubtask(StrictModel):
    name: Literal["scrape", "news", "people", "stack"]
    rationale: str = Field(min_length=3, max_length=300)


class PlannerResult(StrictModel):
    subtasks: list[PlannerSubtask] = Field(min_length=1, max_length=8)
    company_hypothesis: str = Field(min_length=3, max_length=400)
    persona_summary: str = Field(min_length=3, max_length=400)


class ScrapedPage(StrictModel):
    url: HttpUrl
    status: int
    title: str = Field(default="", max_length=400)
    text: str = Field(default="", max_length=20_000)
    headers_seen: dict[str, str] = Field(default_factory=dict)


class ScrapeResult(StrictModel):
    pages: list[ScrapedPage] = Field(default_factory=list, max_length=10)
    canonical_domain: str = Field(min_length=3, max_length=253)
    detected_name: str = Field(default="", max_length=200)


class NewsResult(StrictModel):
    signals: list[NewsSignal] = Field(default_factory=list, max_length=20)
    queries_used: list[str] = Field(default_factory=list, max_length=10)


class PeopleResult(StrictModel):
    people: list[DecisionMaker] = Field(default_factory=list, max_length=20)
    queries_used: list[str] = Field(default_factory=list, max_length=10)


class StackResult(StrictModel):
    stack: list[StackEntry] = Field(default_factory=list, max_length=30)
    detection_methods: list[str] = Field(default_factory=list, max_length=10)


class CritiqueIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=80)
    issue: str = Field(min_length=3, max_length=500)
    severity: Literal["low", "medium", "high"]


class CritiqueResult(StrictModel):
    overall_confidence: float = Field(ge=0.0, le=1.0)
    needs_retry: bool
    issues: list[CritiqueIssue] = Field(default_factory=list, max_length=10)
    summary: str = Field(min_length=3, max_length=600)
