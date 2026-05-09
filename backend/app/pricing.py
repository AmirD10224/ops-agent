"""Model pricing table, versioned. Update PRICING_VERSION when prices change."""

from __future__ import annotations

PRICING_VERSION = "2026-05-01"

# USD per 1M tokens. Source: anthropic.com pricing page snapshot at PRICING_VERSION.
# Conservative estimates, tune when public pricing updates.
_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    # (input_per_mtok, output_per_mtok)
    "claude-opus-4-7": (15.00, 75.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in _PRICES_PER_MTOK:
        # Unknown model, fall back to Sonnet pricing so we never claim $0.
        in_price, out_price = _PRICES_PER_MTOK["claude-sonnet-4-6"]
    else:
        in_price, out_price = _PRICES_PER_MTOK[model]
    return round(
        (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price,
        6,
    )
