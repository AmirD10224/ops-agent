"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { TraceEvent } from "@/lib/types";
import { cn } from "@/lib/cn";

interface Props {
  events: TraceEvent[];
  className?: string;
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function fmtCost(usd?: number): string {
  if (usd === undefined || usd === 0) return "-";
  return usd < 0.001 ? "<$0.001" : `$${usd.toFixed(4)}`;
}

const TYPE_TONE: Record<TraceEvent["type"], { color: string; label: string }> = {
  node_start:  { color: "var(--color-cyan)",       label: "START" },
  node_finish: { color: "var(--color-emerald)",    label: "DONE"  },
  tool_call:   { color: "var(--color-violet)",     label: "TOOL"  },
  run_finish:  { color: "var(--color-chartreuse)", label: "RUN"   },
};

export function TraceLog({ events, className }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const pinned = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    if (pinned) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [events.length]);

  return (
    <div className={cn("panel panel-glow-cyan", className)}>
      <div className="panel-header">
        <span>Telemetry · stream</span>
        <span className="ml-auto tabular text-[var(--color-fg-faint)]">
          {events.length.toString().padStart(3, "0")} events
        </span>
      </div>
      <div
        ref={ref}
        className="h-[420px] overflow-y-auto px-4 py-3 font-mono text-[11.5px]"
      >
        {events.length === 0 ? (
          <div className="text-[var(--color-fg-mute)] italic flex items-center gap-2">
            <span className="inline-block h-1 w-1 rounded-full bg-[var(--color-fg-faint)] pulse" />
            Awaiting first signal…
          </div>
        ) : (
          <ul className="space-y-2">
            <AnimatePresence initial={false}>
              {events.map((e, i) => {
                const tone = TYPE_TONE[e.type];
                return (
                  <motion.li
                    key={`${e.type}-${i}-${e.timestamp}`}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.18 }}
                    className="grid grid-cols-[68px_60px_1fr] gap-3 items-start"
                  >
                    <span className="text-[var(--color-fg-faint)] tabular">
                      {fmtTime(e.timestamp)}
                    </span>
                    <span
                      className="label-mono text-[9.5px] mt-[3px] px-1.5 py-[1px] inline-block border border-current self-start rounded-sm"
                      style={{ color: tone.color }}
                    >
                      {tone.label}
                    </span>
                    <span className="text-[var(--color-fg-dim)] break-words whitespace-pre-wrap leading-snug">
                      {describe(e)}
                    </span>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </div>
  );
}

function describe(e: TraceEvent): string {
  switch (e.type) {
    case "node_start":
      return `${e.node} → start  ${e.input_summary ? "· " + e.input_summary : ""}`;
    case "node_finish": {
      const tokens =
        (e.input_tokens ?? 0) + (e.output_tokens ?? 0) > 0
          ? `  ${e.input_tokens ?? 0}/${e.output_tokens ?? 0} tok`
          : "";
      return `${e.node} → ${e.status}  ${e.duration_ms}ms${tokens}  ${fmtCost(e.cost_usd)}${
        e.notes ? `  · ${e.notes}` : ""
      }`;
    }
    case "tool_call":
      return `${e.node} → ${e.tool}(${e.target.slice(0, 80)}${e.target.length > 80 ? "…" : ""})  ${
        e.success ? "ok" : "fail"
      } ${e.duration_ms}ms${e.error_message ? `  · ${e.error_message}` : ""}`;
    case "run_finish":
      return `RUN ${e.status}  ·  total ${e.total_duration_ms}ms  ·  ${fmtCost(e.total_cost_usd)}`;
  }
}
