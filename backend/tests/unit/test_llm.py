"""LLM wrapper. JSON extraction, repair retry, schema validation."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ConfigDict

from backend.app.agent.llm import call_structured


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int
    s: str


async def test_call_structured_parses_clean_json(fake_anthropic) -> None:  # type: ignore[no-untyped-def]
    fake_anthropic.queue(json.dumps({"n": 7, "s": "ok"}))
    res = await call_structured(
        model="claude-haiku-4-5-20251001",
        system="be brief",
        user="...",
        schema=_Out,
    )
    assert res.parsed.n == 7
    assert res.usage.cost_usd > 0


async def test_call_structured_strips_markdown_fences(fake_anthropic) -> None:  # type: ignore[no-untyped-def]
    fake_anthropic.queue('```json\n{"n": 1, "s": "x"}\n```')
    res = await call_structured(
        model="claude-haiku-4-5-20251001",
        system="be brief",
        user="...",
        schema=_Out,
    )
    assert res.parsed.s == "x"


async def test_call_structured_repairs_broken_json(fake_anthropic) -> None:  # type: ignore[no-untyped-def]
    fake_anthropic.queue("oops not json", out_tok=10)  # bad first
    fake_anthropic.queue(json.dumps({"n": 5, "s": "fixed"}))  # repair second
    res = await call_structured(
        model="claude-haiku-4-5-20251001",
        system="be brief",
        user="...",
        schema=_Out,
    )
    assert res.parsed.n == 5
    # Cost should reflect both calls.
    assert res.usage.input_tokens >= 200


async def test_call_structured_raises_after_repair_still_invalid(fake_anthropic) -> None:  # type: ignore[no-untyped-def]
    fake_anthropic.queue("nope")
    fake_anthropic.queue("still nope")
    with pytest.raises(Exception):
        await call_structured(
            model="claude-haiku-4-5-20251001",
            system="be brief",
            user="...",
            schema=_Out,
        )
