"""Pricing math, guards against silent regressions when model prices change."""

from __future__ import annotations

from backend.app.pricing import cost_usd


def test_haiku_cost() -> None:
    # 1M in, 1M out at (0.80, 4.00) = 4.80 USD
    assert cost_usd("claude-haiku-4-5-20251001", 1_000_000, 1_000_000) == 4.80


def test_sonnet_cost_zero_tokens() -> None:
    assert cost_usd("claude-sonnet-4-6", 0, 0) == 0.0


def test_unknown_model_falls_back_to_sonnet() -> None:
    same = cost_usd("claude-mystery-9", 1000, 1000)
    sonnet = cost_usd("claude-sonnet-4-6", 1000, 1000)
    assert same == sonnet
