# Demo script. 90 seconds

Use this when recording a Loom or walking a buyer through the live demo.

## 0:00. Open the live page

> "This is OpsAgent. It's a multi-step LangGraph agent that takes a company
> URL and a buyer persona, and produces a structured ICP scorecard with a
> recommended outreach angle. What you're about to see is the agent's
> internal trace, streamed live as it runs."

## 0:10. Show the static example first

Click **`/example/linear`**.

> "This is an illustrative fixture replayed at compressed speed, same UI,
> same trace events, no API call. The agent's seven nodes light up in
> order: planner, scraper, news, people, stack detector, synthesizer,
> critic. The fixture has people-research and news-search marked as
> `skipped` rather than fabricated; production runs surface those."

> "Notice news, people, and stack run in parallel, the LangGraph fan-out
> pattern. The critic at the end is what differentiates this from a
> single-shot prompt: it reviews the synthesizer's output, flags
> low-confidence claims, and decides whether the synthesizer should retry."

## 0:35. Point at the trace log

> "Every event is recorded: node start/finish times, tool calls, token
> counts, dollar cost per node. The total cost is right here at the top of
> the scorecard, typically four to six cents per run. Every claim in the
> reasoning section has clickable evidence URLs. Confidence percentages are
> on every claim, these come from the synthesizer and are sanity-checked
> by the critic."

## 0:55. Switch to live mode

Back to `/`. Paste a URL the buyer cares about. Pick a persona. Hit "Run."

> "Same UI, but this time we're hitting a real Modal-deployed API. Watch
> the planner kick off, it uses Claude Haiku 4.5 because the planner is
> a fast routing decision. The synthesizer and critic use Sonnet 4.6
> because that's where the real reasoning happens."

## 1:10. While it runs, show the README

Open the GitHub repo. Highlight:
- Mermaid agent graph
- Test coverage badge
- The ARCHITECTURE.md state diagram
- The eval suite. 25 golden examples, field-wise metrics, judge calibration

> "Coverage is over 85%. Tests cover every node with mocked HTTP via respx
> and a fake Anthropic client, no live API keys needed for CI. There's a
> 25-example eval suite; three examples ship with checked-in fixtures so the
> offline eval scores them on every CI run, the rest auto-skip until they
> have recorded runs. The LLM-judge ships with a documented calibration
> procedure targeting Cohen's κ ≥ 0.7. `evals/calibrate_judge.py` measures
> it once you populate `human_labels.csv`."

## 1:25. Result is in

Click back to the live tab.

> "Run finished in about 50 seconds, four cents. Here's the scorecard:
> ICP fit score, reasoning with citations, decision-makers, all marked
> with confidence, tech stack detected from headers and HTML signatures
> not BuiltWith API, recent news with buyer-relevance commentary, and
> the recommended outreach angle that references at least two specific
> findings from the run. The Langfuse trace link is at the bottom, you
> can see every span, every token, every prompt."

## 1:30. Close

> "If you want this kind of agent for your stack, wired into your CRM,
> your custom personas, your specific tools, message me on Upwork."

---

## What to emphasize in the conversation afterward

- **Production patterns, not framework demos.**
  - Retry/repair at three different layers (network, JSON-parse, critic).
  - Tool errors as values, not exceptions.
  - Versioned prompts in code, not config files that drift.
  - Strict typing end-to-end including the LLM I/O boundary.
- **Honest engineering choices.**
  - No LinkedIn scraping, public snippets only with confidence scoring.
  - No paid stack-detection API. signature inference, swappable.
  - In-process job runner with a clear horizontal-scale path.
- **Reproducibility.**
  - Buyers can clone, `docker compose up`, paste a key, and have the
    full demo running locally in under five minutes.

## Anti-patterns to avoid in the recording

- Don't say "AI" generically, say "Sonnet 4.6 for the synthesizer, Haiku
  4.5 for the planner."
- Don't skip showing the trace log, that's the differentiator.
- Don't pick a controversial company URL during the live demo.
- Don't run a stale persona-to-company pairing, use the defaults that
  match the buyer you're talking to.
