"""Persona resolution rules."""

from __future__ import annotations

import pytest

from backend.app.personas import PERSONAS, list_personas, resolve_persona


def test_list_personas_returns_all() -> None:
    assert {p.id for p in list_personas()} == set(PERSONAS.keys())


def test_resolve_with_preset_id() -> None:
    name, text = resolve_persona("ae_series_b_saas", None)
    assert name == "AE. Series B SaaS"
    assert "Series B–D" in text


def test_resolve_with_freeform_text() -> None:
    name, text = resolve_persona(None, "  custom text  ")
    assert name == "Custom"
    assert text == "custom text"


def test_resolve_preset_plus_text_marks_custom() -> None:
    name, text = resolve_persona("ae_series_b_saas", "override text")
    assert name.endswith("(custom)")
    assert text == "override text"


def test_resolve_requires_one_of_them() -> None:
    with pytest.raises(ValueError):
        resolve_persona(None, None)
    with pytest.raises(ValueError):
        resolve_persona("missing-id", None)
