"use client";

import type { ICPScorecard } from "@/lib/types";
import { cn } from "@/lib/cn";
import { ExternalLink, Linkedin } from "lucide-react";

function scoreTone(score: number): {
  color: string;
  glow: string;
  label: string;
  stamp: "emerald" | "cyan" | "magenta";
} {
  if (score >= 75)
    return {
      color: "var(--color-emerald)",
      glow: "glow-emerald",
      label: "Strong fit",
      stamp: "emerald",
    };
  if (score >= 50)
    return {
      color: "var(--color-cyan)",
      glow: "glow-cyan",
      label: "Moderate fit",
      stamp: "cyan",
    };
  return {
    color: "var(--color-magenta-bright)",
    glow: "glow-magenta",
    label: "Weak fit",
    stamp: "magenta",
  };
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone =
    value >= 0.7
      ? "text-[var(--color-emerald)]"
      : value >= 0.5
        ? "text-[var(--color-cyan)]"
        : "text-[var(--color-magenta-bright)]";
  return (
    <span className={cn("conf-pill", tone)} title={`Confidence: ${pct}%`}>
      <span className="opacity-60">conf</span>
      <span className="tabular">{pct}%</span>
    </span>
  );
}

export function Scorecard({ card }: { card: ICPScorecard }) {
  const tone = scoreTone(card.icp_fit_score);

  return (
    <div className="space-y-6 fade-up">
      {/* HERO STRIP */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-8 panel panel-glow-cyan">
          <div className="panel-header">
            <span>Subject · target evaluation</span>
            <span className="ml-auto stamp" style={{ color: tone.color }}>
              ICP · {card.icp_fit_score}/100
            </span>
          </div>
          <div className="p-7">
            <p className="display text-[var(--color-fg)]" style={{ fontSize: "clamp(40px, 6vw, 72px)" }}>
              {card.company.name}
              <span className="text-[var(--color-fg-faint)]">.</span>
            </p>
            <p className="mt-3 text-[12.5px] font-mono text-[var(--color-fg-mute)] flex flex-wrap items-center gap-x-3 gap-y-1 uppercase tracking-tight">
              <span>{card.company.industry}</span>
              <span className="text-[var(--color-fg-faint)]">·</span>
              <span className="tabular">{card.company.size_estimate} employees</span>
              <span className="text-[var(--color-fg-faint)]">·</span>
              <span className="text-[var(--color-cyan)]">{card.company.domain}</span>
            </p>
            {card.company.description && (
              <p className="mt-5 max-w-2xl text-[14.5px] leading-[1.6] text-[var(--color-fg-dim)] font-sans">
                {card.company.description}
              </p>
            )}
          </div>
        </div>

        <div className="lg:col-span-4 panel relative overflow-hidden" style={{ boxShadow: `inset 0 1px 0 ${tone.color}1a, 0 0 0 1px ${tone.color}14` }}>
          <div
            aria-hidden
            className="absolute -top-12 -right-12 h-40 w-40 rounded-full blur-3xl opacity-40"
            style={{ background: tone.color }}
          />
          <div className="panel-header">
            <span>ICP Fit Score</span>
            <span className="ml-auto stamp" style={{ color: tone.color }}>
              {tone.label}
            </span>
          </div>
          <div className="px-6 pt-6 pb-6 relative">
            <p
              className={`display-mono ${tone.glow}`}
              style={{
                fontSize: "clamp(80px, 12vw, 144px)",
                color: tone.color,
                lineHeight: 0.85,
              }}
            >
              {card.icp_fit_score}
            </p>
            <p className="mt-1 text-[10.5px] uppercase tracking-[0.18em] text-[var(--color-fg-mute)]">
              of 100 · vs persona
            </p>
            <div className="mt-5 h-1.5 bg-[var(--color-line)] rounded-sm overflow-hidden">
              <div
                className="h-full rounded-sm"
                style={{
                  width: `${card.icp_fit_score}%`,
                  background: `linear-gradient(90deg, ${tone.color}55, ${tone.color})`,
                  boxShadow: `0 0 12px ${tone.color}`,
                }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* WARNINGS */}
      {card.confidence_warnings.length > 0 && (
        <section className="panel panel-glow-magenta">
          <div className="panel-header panel-header-magenta">
            <span>Caveats · low-confidence flags</span>
            <span className="ml-auto stamp stamp-magenta">{card.confidence_warnings.length}</span>
          </div>
          <ul className="p-5 space-y-2">
            {card.confidence_warnings.map((w, i) => (
              <li key={i} className="text-[13px] text-[var(--color-fg-dim)] flex gap-2.5">
                <span className="text-[var(--color-magenta-bright)] tabular shrink-0">▸</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* OUTREACH ANGLE */}
      <section className="panel panel-glow-violet">
        <div className="panel-header panel-header-violet">
          <span>Recommended outreach angle</span>
          <span className="ml-auto stamp stamp-violet">Strategic</span>
        </div>
        <div className="p-7">
          <p
            className="display text-[var(--color-fg)] leading-[1.3] max-w-3xl"
            style={{ fontSize: "clamp(20px, 2.4vw, 28px)" }}
          >
            <span className="text-[var(--color-violet)]">&ldquo;</span>
            {card.recommended_outreach_angle}
            <span className="text-[var(--color-violet)]">&rdquo;</span>
          </p>
        </div>
      </section>

      {/* REASONING */}
      <section>
        <SectionRule chip="§A" title="Reasoning" sub={`${card.icp_reasoning.length} claims`} />
        <ol className="space-y-3">
          {card.icp_reasoning.map((r, i) => (
            <li key={i} className="panel grid grid-cols-[60px_1fr_auto] gap-5 px-6 py-5 items-start">
              <span
                className="display-mono text-[var(--color-cyan)] glow-cyan tabular"
                style={{ fontSize: 32, lineHeight: 1 }}
              >
                {String(i + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0">
                <p className="text-[14.5px] leading-[1.55] text-[var(--color-fg)] font-sans">
                  {r.claim}
                </p>
                {r.evidence.length > 0 && (
                  <ul className="mt-4 space-y-2 pt-3 border-t border-[var(--color-line-2)]">
                    {r.evidence.map((e, j) => (
                      <li
                        key={j}
                        className="text-[12px] flex gap-2.5 items-baseline"
                      >
                        <span className="font-mono tabular text-[var(--color-fg-faint)] shrink-0">
                          [{String(j + 1).padStart(2, "0")}]
                        </span>
                        <div className="min-w-0">
                          <a
                            href={e.url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="inline-flex items-center gap-1 text-[var(--color-cyan)] hover:text-[var(--color-cyan-bright)] transition-colors font-medium"
                          >
                            <ExternalLink size={11} />
                            {e.title}
                          </a>
                          {e.snippet && (
                            <span className="text-[var(--color-fg-mute)] ml-2">
                              &mdash; &ldquo;{e.snippet}&rdquo;
                            </span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <ConfidenceBadge value={r.confidence} />
            </li>
          ))}
        </ol>
      </section>

      {/* TWO-UP: stack + people */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section>
          <SectionRule chip="§B" title="Tech stack" sub={`${card.tech_stack.length} signatures`} tone="violet" />
          <div className="panel panel-glow-violet">
            {card.tech_stack.length === 0 ? (
              <p className="p-6 text-[13px] text-[var(--color-fg-mute)] italic">
                No public signatures detected.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-px bg-[var(--color-line)]">
                {card.tech_stack.map((s, i) => (
                  <div
                    key={i}
                    className="bg-[var(--color-panel)] p-4 hover:bg-[var(--color-panel-hi)] transition-colors min-h-[110px] flex flex-col justify-between"
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span className="label-mono text-[9.5px] text-[var(--color-fg-mute)]">
                        {s.category}
                      </span>
                      <ConfidenceBadge value={s.confidence} />
                    </div>
                    <p className="display text-[var(--color-fg)] text-[20px] leading-[1.05] mb-2">
                      {s.tool}
                    </p>
                    <p className="text-[10.5px] text-[var(--color-fg-mute)] leading-snug font-mono">
                      ▸ {s.evidence}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section>
          <SectionRule chip="§C" title="Decision-makers" sub={`${card.decision_makers.length} identified`} tone="magenta" />
          <div className="panel panel-glow-magenta">
            {card.decision_makers.length === 0 ? (
              <p className="p-6 text-[13px] text-[var(--color-fg-mute)] italic">
                None inferred from public sources.
              </p>
            ) : (
              <ul>
                {card.decision_makers.map((p, i) => (
                  <li
                    key={i}
                    className={cn(
                      "p-5",
                      i < card.decision_makers.length - 1 &&
                        "border-b border-[var(--color-line-2)]",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="display text-[var(--color-fg)] text-[18px] leading-[1.1]">
                          {p.name}
                        </p>
                        <p className="label-mono text-[10px] text-[var(--color-magenta-bright)] mt-1">
                          {p.title}
                        </p>
                      </div>
                      <ConfidenceBadge value={p.confidence} />
                    </div>
                    <p className="text-[12.5px] text-[var(--color-fg-dim)] mt-3 leading-snug">
                      {p.relevance}
                    </p>
                    {p.linkedin && (
                      <a
                        href={p.linkedin}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="mt-2 inline-flex items-center gap-1.5 text-[11.5px] text-[var(--color-cyan)] hover:text-[var(--color-cyan-bright)] transition-colors"
                      >
                        <Linkedin size={12} />
                        Open profile
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>

      {/* RECENT SIGNALS */}
      <section>
        <SectionRule chip="§D" title="Recent signals" sub={`${card.recent_signals.length} items`} tone="chartreuse" />
        <div className="panel panel-glow-chartreuse">
          {card.recent_signals.length === 0 ? (
            <p className="p-6 text-[13px] text-[var(--color-fg-mute)] italic">
              No recent public signals found.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--color-line-2)]">
              {card.recent_signals.map((s, i) => (
                <li
                  key={i}
                  className="p-5 grid grid-cols-[80px_1fr_auto] gap-5 items-start hover:bg-[var(--color-panel-2)] transition-colors"
                >
                  <span className="label-mono text-[10px] text-[var(--color-fg-mute)] tabular pt-0.5">
                    {s.date ?? "-"}
                  </span>
                  <div>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-[15px] font-sans font-medium text-[var(--color-fg)] hover:text-[var(--color-chartreuse)] transition-colors block leading-[1.35]"
                    >
                      {s.headline}
                    </a>
                    <p className="text-[11.5px] text-[var(--color-fg-mute)] mt-2 leading-snug">
                      ▸ {s.buyer_relevance}
                    </p>
                  </div>
                  <ConfidenceBadge value={s.confidence} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* COLOPHON */}
      <section className="panel p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className={`stamp stamp-${tone.stamp}`}>Verified</span>
          <p className="text-[12px] font-mono text-[var(--color-fg-mute)]">
            Estimated research cost ·{" "}
            <span className="text-[var(--color-cyan)] tabular">
              ${card.estimated_research_cost_usd.toFixed(4)}
            </span>
          </p>
        </div>
        {card.trace_url && (
          <a
            href={card.trace_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1.5 text-[12px] text-[var(--color-violet)] hover:text-[var(--color-violet-bright)] transition-colors label-mono"
          >
            <ExternalLink size={12} />
            Open Langfuse trace
          </a>
        )}
      </section>
    </div>
  );
}

function SectionRule({
  chip,
  title,
  sub,
  tone = "cyan",
}: {
  chip: string;
  title: string;
  sub?: string;
  tone?: "cyan" | "violet" | "magenta" | "chartreuse";
}) {
  const c = {
    cyan: "var(--color-cyan)",
    violet: "var(--color-violet)",
    magenta: "var(--color-magenta-bright)",
    chartreuse: "var(--color-chartreuse-bright)",
  }[tone];
  return (
    <div className="section-rule">
      <span
        className="section-rule__chip"
        style={{ color: c, borderColor: c, background: `${c}0d` }}
      >
        {chip}
      </span>
      <span className="section-rule__title">{title}</span>
      <span className="section-rule__line" />
      {sub && (
        <span className="text-[10.5px] font-mono text-[var(--color-fg-mute)] uppercase tracking-[0.16em]">
          {sub}
        </span>
      )}
    </div>
  );
}
