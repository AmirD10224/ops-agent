"""Built-in buyer personas. Buyers can also pass freeform text."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Persona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=20, max_length=2000)


PERSONAS: dict[str, Persona] = {
    "ae_series_b_saas": Persona(
        id="ae_series_b_saas",
        name="AE. Series B SaaS",
        description=(
            "Account executive selling a $50–250k ACV B2B SaaS product to RevOps and "
            "Sales leadership. ICP: Series B–D SaaS companies, 50–500 employees, "
            "engineering-heavy, growing GTM team. Pain points we solve: pipeline "
            "visibility, forecast accuracy, rep ramp time. Typical buying committee: "
            "VP Sales, VP RevOps, CRO, with Sales Ops Manager as champion. "
            "We win when prospects already use Salesforce + a modern data stack "
            "(Snowflake/dbt) and have hired a dedicated RevOps lead."
        ),
    ),
    "revops_plg": Persona(
        id="revops_plg",
        name="RevOps Director. PLG",
        description=(
            "Head of Revenue Operations at a product-led B2B SaaS company. ICP: "
            "PLG companies with self-serve + sales-assist motion, 100–1000 employees, "
            "$10M–$100M ARR. Cares about: PQL conversion, expansion revenue, "
            "instrumentation gaps between product analytics and CRM. Wins: when the "
            "prospect has Segment/RudderStack, hybrid Salesforce+HubSpot, and a "
            "named PLG motion in their last earnings or blog post."
        ),
    ),
    "sdr_seed_founder": Persona(
        id="sdr_seed_founder",
        name="Founder/SDR. Seed B2B",
        description=(
            "Seed-stage founder running outbound personally before a first sales "
            "hire. ICP: companies that just raised seed/Series A in last 6 months, "
            "5–30 employees, building horizontal infra/dev tools, technical founders. "
            "Pain: writing first cold emails, finding ICP, manual research time. "
            "Wins: prospect has a clear technical post-mortem or engineering blog, "
            "is hiring engineers, and has a recent fundraise news post."
        ),
    ),
}


def list_personas() -> list[Persona]:
    return list(PERSONAS.values())


def resolve_persona(persona_id: str | None, persona_text: str | None) -> tuple[str, str]:
    """Return (name, text), supports preset id, freeform text, or both."""
    if persona_text and persona_text.strip():
        if persona_id and persona_id in PERSONAS:
            return PERSONAS[persona_id].name + " (custom)", persona_text.strip()
        return "Custom", persona_text.strip()
    if persona_id and persona_id in PERSONAS:
        p = PERSONAS[persona_id]
        return p.name, p.description
    raise ValueError(
        "Either persona_id (one of: " + ", ".join(PERSONAS) + ") or persona_text required"
    )
