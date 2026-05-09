"use client";

import { useEffect, useMemo, useState } from "react";
import { AgentGraph } from "./AgentGraph";
import { TraceLog } from "./TraceLog";
import { Scorecard } from "./Scorecard";
import {
  type ICPScorecard,
  type NodeName,
  type NodeStatus,
  NODE_ORDER,
  type TraceEvent,
} from "@/lib/types";

interface ExampleData {
  id: string;
  company_url: string;
  persona_name: string;
  total_cost_usd: number;
  scorecard: ICPScorecard;
  events: Array<{ seq: number; type: string; timestamp: string; payload: TraceEvent }>;
}

const INITIAL: Record<NodeName, NodeStatus> = Object.fromEntries(
  NODE_ORDER.map((n) => [n, "pending" as const]),
) as Record<NodeName, NodeStatus>;

export function StaticExampleViewer({ data }: { data: ExampleData }) {
  const [eventsShown, setEventsShown] = useState<TraceEvent[]>([]);
  const [done, setDone] = useState(false);
  const [showScore, setShowScore] = useState(false);

  const timed = useMemo(() => {
    const evs = data.events.map((e) => e.payload);
    if (!evs.length) return [];
    const t0 = Date.parse(evs[0].timestamp);
    const last = Date.parse(evs[evs.length - 1].timestamp);
    const span = Math.max(1, last - t0);
    const target = 8000;
    return evs.map((e) => ({
      event: e,
      offsetMs: ((Date.parse(e.timestamp) - t0) / span) * target,
    }));
  }, [data]);

  useEffect(() => {
    setEventsShown([]);
    setDone(false);
    setShowScore(false);
    const timers: ReturnType<typeof setTimeout>[] = [];
    timed.forEach(({ event, offsetMs }) => {
      timers.push(
        setTimeout(() => {
          setEventsShown((prev) => [...prev, event]);
          if (event.type === "run_finish") {
            setDone(true);
            timers.push(setTimeout(() => setShowScore(true), 300));
          }
        }, offsetMs),
      );
    });
    return () => timers.forEach(clearTimeout);
  }, [timed]);

  const nodeStates: Record<NodeName, NodeStatus> = useMemo(() => {
    const s = { ...INITIAL };
    for (const e of eventsShown) {
      if (e.type === "node_start") s[e.node] = "running";
      else if (e.type === "node_finish") s[e.node] = e.status;
    }
    return s;
  }, [eventsShown]);

  const completedCount = useMemo(
    () => Object.values(nodeStates).filter((s) => s === "done").length,
    [nodeStates],
  );

  return (
    <div className="space-y-6">
      {/* Replay banner */}
      <div className="panel panel-glow-violet p-5 flex flex-wrap items-center gap-4">
        <span className="stamp stamp-violet">Recorded</span>
        <span className="text-[12.5px] font-mono">
          <span className="text-[var(--color-cyan)]">{data.company_url}</span>
          <span className="text-[var(--color-fg-faint)] mx-2">·</span>
          <span className="text-[var(--color-fg-dim)]">{data.persona_name}</span>
        </span>
        <span className="ml-auto flex items-center gap-3 text-[12px] font-mono text-[var(--color-fg-mute)]">
          <span>
            Cost ·{" "}
            <span className="text-[var(--color-cyan)] tabular">
              ${data.total_cost_usd.toFixed(4)}
            </span>
          </span>
          {!done && (
            <span className="flex items-center gap-1.5 text-[var(--color-chartreuse-bright)] uppercase tracking-[0.16em]">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-chartreuse)] pulse shadow-[0_0_6px_var(--color-chartreuse)]" />
              Replaying
            </span>
          )}
          {done && (
            <span className="flex items-center gap-1.5 text-[var(--color-emerald)] uppercase tracking-[0.16em]">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-emerald)] shadow-[0_0_6px_var(--color-emerald)]" />
              Complete
            </span>
          )}
        </span>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Nodes complete" value={`${completedCount}/7`} tone="cyan" />
        <Kpi label="Cost" value={`$${data.total_cost_usd.toFixed(4)}`} tone="violet" />
        <Kpi label="Events" value={String(eventsShown.length)} tone="magenta" />
        <Kpi label="Status" value={done ? "DONE" : "REPLAYING"} tone={done ? "emerald" : "chartreuse"} />
      </div>

      {/* Graph + telemetry */}
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
        <TraceLog events={eventsShown} />
      </div>

      {/* Scorecard */}
      {showScore && (
        <div>
          <header className="section-rule">
            <span className="section-rule__chip">§ Briefing</span>
            <span className="section-rule__title">Output</span>
            <span className="section-rule__line" />
            <span className="stamp stamp-emerald">Verified</span>
          </header>
          <Scorecard card={data.scorecard} />
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
