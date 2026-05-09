"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import { AgentGraph } from "./AgentGraph";
import { TraceLog } from "./TraceLog";
import { Scorecard } from "./Scorecard";
import {
  fetchRun,
  startRun,
  subscribeStream,
  type StartRunResponse,
} from "@/lib/api";
import {
  type ICPScorecard,
  type NodeName,
  type NodeStatus,
  NODE_ORDER,
  type Persona,
  type TraceEvent,
} from "@/lib/types";

const INITIAL_NODE_STATES: Record<NodeName, NodeStatus> = Object.fromEntries(
  NODE_ORDER.map((n) => [n, "pending" as const]),
) as Record<NodeName, NodeStatus>;

interface Props {
  personas: Persona[];
}

export function RunPanel({ personas }: Props) {
  const [companyUrl, setCompanyUrl] = useState("https://linear.app");
  const [personaId, setPersonaId] = useState(personas[0]?.id ?? "");
  const [customText, setCustomText] = useState("");
  const [showCustom, setShowCustom] = useState(false);

  const [run, setRun] = useState<StartRunResponse | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [scorecard, setScorecard] = useState<ICPScorecard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const nodeStates: Record<NodeName, NodeStatus> = useMemo(() => {
    const s = { ...INITIAL_NODE_STATES };
    for (const e of events) {
      if (e.type === "node_start") s[e.node] = "running";
      else if (e.type === "node_finish") s[e.node] = e.status;
    }
    return s;
  }, [events]);

  // Cost & latency rollups
  const totalCost = useMemo(
    () =>
      events.reduce(
        (sum, e) => (e.type === "node_finish" ? sum + (e.cost_usd ?? 0) : sum),
        0,
      ),
    [events],
  );
  const totalDuration = useMemo(
    () =>
      events.reduce(
        (sum, e) =>
          e.type === "node_finish" ? sum + (e.duration_ms ?? 0) : sum,
        0,
      ),
    [events],
  );
  const completedCount = useMemo(
    () => Object.values(nodeStates).filter((s) => s === "done").length,
    [nodeStates],
  );

  useEffect(() => {
    if (!run) return;
    const unsub = subscribeStream(
      run.job_id,
      (e) => {
        setEvents((prev) => {
          const key = `${e.type}:${e.timestamp}:${"node" in e ? e.node : ""}`;
          if (
            prev.some(
              (p) =>
                `${p.type}:${p.timestamp}:${"node" in p ? p.node : ""}` === key,
            )
          ) {
            return prev;
          }
          return [...prev, e];
        });
        if (e.type === "run_finish") {
          setRunning(false);
          if (e.status === "done") {
            fetchRun(run.job_id)
              .then((r) => {
                if (r.scorecard) setScorecard(r.scorecard);
              })
              .catch((err: Error) => {
                setError(`Could not load scorecard: ${err.message}`);
              });
          } else {
            setError("Run failed.");
          }
        }
      },
      (err) => setError(err.message),
    );
    return unsub;
  }, [run]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setEvents([]);
    setScorecard(null);
    setRun(null);
    setRunning(true);
    try {
      const r = await startRun({
        company_url: companyUrl.trim(),
        persona_id: showCustom && customText.trim() ? null : personaId,
        persona_text: showCustom ? customText.trim() : null,
      });
      setRun(r);
    } catch (err) {
      setError((err as Error).message);
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* INTEL REQUEST FORM */}
      <form onSubmit={onSubmit} className="panel panel-glow-cyan">
        <div className="panel-header">
          <span>Tasking · dispatch agent</span>
          <span className="ml-auto stamp stamp-cyan">F-1</span>
        </div>

        <div className="p-5 md:p-6 grid grid-cols-1 md:grid-cols-[1fr_300px_auto] gap-4 items-end">
          <div>
            <label className="label-mono text-[10.5px] text-[var(--color-fg-mute)] block mb-2">
              Target · company URL
            </label>
            <input
              required
              value={companyUrl}
              onChange={(e) => setCompanyUrl(e.target.value)}
              placeholder="https://linear.app"
              className="w-full bg-[var(--color-bg-2)] border border-[var(--color-line-2)] px-3.5 py-2.5 outline-none focus:border-[var(--color-cyan)] font-mono text-[13.5px] text-[var(--color-fg)] rounded-md"
            />
          </div>
          <div>
            <label className="label-mono text-[10.5px] text-[var(--color-fg-mute)] block mb-2">
              Buyer · persona
            </label>
            <select
              value={personaId}
              onChange={(e) => setPersonaId(e.target.value)}
              disabled={showCustom}
              className="w-full bg-[var(--color-bg-2)] border border-[var(--color-line-2)] px-3.5 py-2.5 outline-none focus:border-[var(--color-cyan)] text-[13px] text-[var(--color-fg)] disabled:opacity-50 rounded-md"
            >
              {personas.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <button
              type="submit"
              disabled={running}
              className="group inline-flex items-center justify-center gap-2 h-[42px] px-5 text-[var(--color-bg)] font-semibold tracking-tight text-[13px] rounded-md disabled:opacity-50 w-full md:w-auto transition-[background-position,box-shadow] duration-500"
              style={{
                background:
                  "linear-gradient(90deg, var(--color-cyan) 0%, var(--color-violet) 50%, var(--color-cyan) 100%)",
                backgroundSize: "200% 100%",
                boxShadow: "0 8px 24px -8px rgba(34, 211, 238, 0.6)",
              }}
            >
              {running ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Running…
                </>
              ) : (
                <>
                  <Sparkles className="size-3.5" />
                  Dispatch
                  <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
                </>
              )}
            </button>
          </div>
        </div>

        <div className="px-5 md:px-6 pb-5">
          <button
            type="button"
            onClick={() => setShowCustom((s) => !s)}
            className="text-[11px] font-mono text-[var(--color-fg-mute)] hover:text-[var(--color-cyan)] transition-colors uppercase tracking-[0.14em]"
          >
            {showCustom ? "← Use preset persona" : "+ Use custom persona"}
          </button>
          {showCustom && (
            <textarea
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              placeholder="Describe the ICP, who you sell to, win conditions, pain points, buying committee, win signals…"
              className="mt-3 w-full h-28 bg-[var(--color-bg-2)] border border-[var(--color-line-2)] px-3.5 py-2.5 outline-none focus:border-[var(--color-cyan)] text-[13px] text-[var(--color-fg)] rounded-md font-sans"
            />
          )}
          {error && (
            <div className="mt-4 p-3 border border-[var(--color-magenta)] bg-[var(--color-bg-2)] text-[12.5px] text-[var(--color-magenta-bright)] flex items-center gap-2 rounded-md">
              <span className="stamp stamp-magenta">Fail</span>
              {error}
            </div>
          )}
        </div>
      </form>

      {/* KPI strip, visible during/after run */}
      {(running || events.length > 0) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Kpi label="Nodes complete" value={`${completedCount}/7`} tone="cyan" />
          <Kpi
            label="Cost · live"
            value={`$${totalCost.toFixed(4)}`}
            tone="violet"
          />
          <Kpi
            label="Duration"
            value={`${(totalDuration / 1000).toFixed(2)}s`}
            tone="magenta"
          />
          <Kpi
            label="Status"
            value={running ? "RUNNING" : scorecard ? "DONE" : "PENDING"}
            tone={running ? "chartreuse" : scorecard ? "emerald" : "violet"}
          />
        </div>
      )}

      {/* GRAPH + TELEMETRY */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_440px] gap-4">
        <section className="panel panel-glow-violet">
          <div className="panel-header panel-header-violet">
            <span>Operation graph · 7 nodes</span>
            <span className="ml-auto tabular text-[var(--color-fg-faint)]">
              1 fan-out · 1 critic loop
            </span>
          </div>
          <div className="p-5">
            <AgentGraph nodeStates={nodeStates} />
          </div>
        </section>
        <TraceLog events={events} />
      </div>

      {/* SCORECARD */}
      {scorecard && (
        <div>
          <header className="section-rule">
            <span className="section-rule__chip">§ Briefing</span>
            <span className="section-rule__title">Output</span>
            <span className="section-rule__line" />
            <span className="stamp stamp-emerald">Verified</span>
          </header>
          <Scorecard card={scorecard} />
        </div>
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "cyan" | "violet" | "magenta" | "chartreuse" | "emerald";
}) {
  const c = {
    cyan: "var(--color-cyan)",
    violet: "var(--color-violet-bright)",
    magenta: "var(--color-magenta-bright)",
    chartreuse: "var(--color-chartreuse-bright)",
    emerald: "var(--color-emerald)",
  }[tone];
  const glow = {
    cyan: "glow-cyan",
    violet: "glow-violet",
    magenta: "glow-magenta",
    chartreuse: "glow-chartreuse",
    emerald: "glow-emerald",
  }[tone];
  return (
    <div className="panel relative overflow-hidden p-4">
      <div
        aria-hidden
        className="absolute -top-10 -right-10 h-24 w-24 rounded-full blur-3xl opacity-20"
        style={{ background: c }}
      />
      <p className="label-mono text-[10px] text-[var(--color-fg-mute)] mb-1.5">
        {label}
      </p>
      <p
        className={`display-mono ${glow}`}
        style={{ fontSize: 24, color: c }}
      >
        {value}
      </p>
    </div>
  );
}
