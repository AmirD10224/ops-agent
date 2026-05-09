"""LangGraph wiring.

Topology
--------
    PLANNER  →  SCRAPER  →  ┬→ NEWS    ┐
                            ├→ PEOPLE  ├→ SYNTHESIZER → CRITIC ─┐
                            └→ STACK   ┘         ▲              │
                                                 └── retry ─────┘
                                                                 → END

We deliberately chain SCRAPER ahead of (NEWS, PEOPLE, STACK), the spec describes
all four as parallel, but in practice STACK detection and the company-name token
used by NEWS/PEOPLE both improve with scrape output. We keep the three downstream
tools parallel so the demo still showcases concurrent fan-out, and document this
refinement explicitly in ARCHITECTURE.md.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.app.agent.nodes.critic import run_critic
from backend.app.agent.nodes.news import run_news
from backend.app.agent.nodes.people import run_people
from backend.app.agent.nodes.planner import run_planner
from backend.app.agent.nodes.scraper import run_scraper
from backend.app.agent.nodes.stack import run_stack
from backend.app.agent.nodes.synthesizer import run_synthesizer
from backend.app.agent.runtime import RunContext
from backend.app.config import get_settings
from backend.app.schemas.state import AgentState


def _ctx(config: RunnableConfig) -> RunContext:
    raw = config.get("configurable", {})
    ctx = raw.get("ctx")
    if not isinstance(ctx, RunContext):
        raise RuntimeError("RunContext missing in graph config['configurable']['ctx']")
    return ctx


# Node adapters: convert LangGraph signature → our (state, ctx=...) call.
async def _planner(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    return await run_planner(state, ctx=_ctx(config))


async def _scraper(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    return await run_scraper(state, ctx=_ctx(config))


async def _news(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    return await run_news(state, ctx=_ctx(config))


async def _people(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    return await run_people(state, ctx=_ctx(config))


async def _stack(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    return await run_stack(state, ctx=_ctx(config))


async def _synth(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    update: dict[str, Any] = dict(await run_synthesizer(state, ctx=_ctx(config)))
    # Carry the counter forward unchanged, critic increments after its own pass.
    update["critic_passes"] = state.critic_passes
    return update


async def _critic(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    update: dict[str, Any] = dict(await run_critic(state, ctx=_ctx(config)))
    update["critic_passes"] = state.critic_passes + 1
    return update


def _route_after_critic(state: AgentState) -> Literal["synthesizer", "__end__"]:
    settings = get_settings()
    if (
        state.critique is not None
        and state.critique.needs_retry
        and state.critic_passes <= settings.max_critic_retries
    ):
        return "synthesizer"
    return "__end__"


def build_graph() -> Any:
    """Compile and return the runnable LangGraph."""
    g: StateGraph[AgentState] = StateGraph(AgentState)

    g.add_node("planner", _planner)
    g.add_node("scraper", _scraper)
    g.add_node("news", _news)
    g.add_node("people", _people)
    g.add_node("stack", _stack)
    g.add_node("synthesizer", _synth)
    g.add_node("critic", _critic)

    g.set_entry_point("planner")
    g.add_edge("planner", "scraper")

    # Fan out: scraper → (news, people, stack) in parallel
    g.add_edge("scraper", "news")
    g.add_edge("scraper", "people")
    g.add_edge("scraper", "stack")

    # Barrier: synthesizer waits for all three
    g.add_edge("news", "synthesizer")
    g.add_edge("people", "synthesizer")
    g.add_edge("stack", "synthesizer")

    g.add_edge("synthesizer", "critic")
    g.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"synthesizer": "synthesizer", "__end__": END},
    )

    return g.compile()
