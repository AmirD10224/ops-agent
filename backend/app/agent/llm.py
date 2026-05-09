"""Anthropic call wrapper that returns parsed Pydantic models.

Centralizes:
 - JSON-mode prompting (we ask for JSON in the system prompt and parse it)
 - Structured retries on parse / validation failure (one repair round)
 - Token + cost accounting
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TypeVar

from anthropic import APIError, APIStatusError
from pydantic import BaseModel, ValidationError

from backend.app.clients import get_anthropic
from backend.app.logging_setup import get_logger
from backend.app.pricing import cost_usd

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

REPAIR_INSTRUCTION = (
    "Your previous response could not be parsed as valid JSON for the schema. "
    "Return ONLY valid JSON matching the schema. Error: {error}\n"
    "Previous response (truncated):\n{previous}"
)


@dataclass(frozen=True, slots=True)
class LLMUsage:
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str


@dataclass(frozen=True, slots=True)
class StructuredCall[T: BaseModel]:
    parsed: T
    usage: LLMUsage
    raw_text: str


def _strip_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        # remove ```json ... ``` or ``` ... ```
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1 :]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def _extract_json(text: str) -> str:
    """Best-effort JSON extraction.

    Trims markdown fences, then walks the string with a brace counter +
    string/escape state machine so we extract exactly the first balanced
    ``{...}`` block, naive ``s.rfind('}')`` would mis-match when the
    response wraps multiple JSON-shaped blobs in commentary.
    """
    s = _strip_fences(text)
    if not s:
        return s
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    # Unbalanced, return from the first brace, let the caller's repair retry handle it.
    return s[start:]


async def call_structured[T: BaseModel](
    *,
    model: str,
    system: str,
    user: str,
    schema: type[T],
    max_tokens: int = 2000,
    temperature: float = 0.2,
) -> StructuredCall[T]:
    """Invoke Claude, parse JSON, validate against schema. One repair retry on bad JSON."""
    client = get_anthropic()

    async def _call(messages: list[dict[str, str]]) -> tuple[str, int, int]:
        try:
            resp = await client.messages.create(
                model=model,
                system=system,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except APIStatusError as e:
            log.warning("llm.api_status_error", model=model, status=e.status_code)
            raise
        except APIError as e:
            log.warning("llm.api_error", model=model, error=str(e))
            raise
        text_blocks = [
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"
        ]
        text = "\n".join(t for t in text_blocks if t)
        if not text:
            # No text blocks, refusal, content filter, or pure-tool-use response.
            # Fail loudly rather than feeding empty assistant content into a
            # repair turn (which Anthropic rejects).
            raise ValueError(
                f"model returned no text blocks (model={model}, "
                f"stop_reason={getattr(resp, 'stop_reason', '?')})"
            )
        return text, resp.usage.input_tokens, resp.usage.output_tokens

    messages: list[dict[str, str]] = [{"role": "user", "content": user}]

    text, in_tok, out_tok = await _call(messages)
    total_in, total_out = in_tok, out_tok

    try:
        parsed = schema.model_validate_json(_extract_json(text))
    except (ValidationError, ValueError, json.JSONDecodeError) as first_err:
        # One repair round.
        log.info("llm.repair_attempt", model=model, error=str(first_err)[:200])
        repair_user = REPAIR_INSTRUCTION.format(error=str(first_err)[:400], previous=text[:1500])
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": repair_user})
        text2, in2, out2 = await _call(messages)
        total_in += in2
        total_out += out2
        parsed = schema.model_validate_json(_extract_json(text2))
        text = text2  # report repaired text as raw

    return StructuredCall(
        parsed=parsed,
        raw_text=text,
        usage=LLMUsage(
            input_tokens=total_in,
            output_tokens=total_out,
            cost_usd=cost_usd(model, total_in, total_out),
            model=model,
        ),
    )
