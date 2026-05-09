"""Prompt registry. Versioning: each prompt is keyed (name, version).

Why versioned in code: prompts are hot-path config; bumping a version forces a
deliberate code review, surfaces in git blame, and lets evals pin to a specific
prompt the way they pin to a specific model.
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).parent

PROMPT_VERSIONS = {
    "planner": "v1",
    "synthesizer": "v1",
    "critic": "v1",
}


def load(name: str) -> str:
    version = PROMPT_VERSIONS[name]
    path = _DIR / f"{name}.{version}.md"
    return path.read_text(encoding="utf-8")
