"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { NodeName, NodeStatus } from "@/lib/types";
import { cn } from "@/lib/cn";

interface NodeBox {
  name: NodeName;
  label: string;
  sub: string;
  x: number;
  y: number;
  tone: "cyan" | "violet" | "magenta" | "chartreuse";
}

const NODES: NodeBox[] = [
  { name: "planner",     label: "PLANNER",     sub: "haiku 4.5",       x:  90, y: 220, tone: "cyan" },
  { name: "scraper",     label: "SCRAPER",     sub: "httpx · selectolax", x: 280, y: 220, tone: "cyan" },
  { name: "news",        label: "NEWS",        sub: "tavily · search",    x: 480, y:  90, tone: "violet" },
  { name: "people",      label: "PEOPLE",      sub: "tavily · linkedin",  x: 480, y: 220, tone: "violet" },
  { name: "stack",       label: "STACK",       sub: "header sigs",        x: 480, y: 350, tone: "violet" },
  { name: "synthesizer", label: "SYNTHESIZER", sub: "sonnet 4.6",         x: 700, y: 220, tone: "magenta" },
  { name: "critic",      label: "CRITIC",      sub: "self-review",        x: 880, y: 220, tone: "chartreuse" },
];

const EDGES: Array<[NodeName, NodeName]> = [
  ["planner", "scraper"],
  ["scraper", "news"],
  ["scraper", "people"],
  ["scraper", "stack"],
  ["news", "synthesizer"],
  ["people", "synthesizer"],
  ["stack", "synthesizer"],
  ["synthesizer", "critic"],
];

const NODE_BY_NAME: Record<NodeName, NodeBox> = Object.fromEntries(
  NODES.map((n) => [n.name, n]),
) as Record<NodeName, NodeBox>;

const TONE_COLOR = {
  cyan: "#f0b366",       // amber primary (was electric cyan)
  violet: "#f0b366",     // collapsed to primary
  magenta: "#f0b366",    // collapsed to primary
  chartreuse: "#5cf2c7", // mint, used only for final/critic
} as const;

const STATUS_COLOR: Record<NodeStatus, string> = {
  pending: "#404562",
  running: "#f0b366",
  done:    "#5cf2c7",
  failed:  "#f87171",
  skipped: "#6b6f88",
};

export interface AgentGraphProps {
  nodeStates: Record<NodeName, NodeStatus>;
  className?: string;
}

export function AgentGraph({ nodeStates, className }: AgentGraphProps) {
  const W = 960;
  const H = 440;

  // Animated particle phase
  const [t, setT] = useState(0);
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = now - last;
      last = now;
      setT((x) => x + dt);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className={cn("relative", className)}>
      {/* a11y mirror */}
      <ul
        role="status"
        aria-live="polite"
        aria-atomic="false"
        className="sr-only absolute h-px w-px overflow-hidden whitespace-nowrap"
      >
        {NODES.map((node) => (
          <li key={`a11y-${node.name}`}>
            {node.label}: {nodeStates[node.name]}
          </li>
        ))}
      </ul>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block" role="img">
        <defs>
          <pattern id="dots" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="0.5" cy="0.5" r="0.5" fill="rgba(255,255,255,0.04)" />
          </pattern>
          <linearGradient id="edge-cyan" x1="0" x2="1">
            <stop offset="0%" stopColor="#f0b366" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#f0b366" stopOpacity="0.7" />
          </linearGradient>
          <linearGradient id="edge-violet" x1="0" x2="1">
            <stop offset="0%" stopColor="#f0b366" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#f0b366" stopOpacity="0.7" />
          </linearGradient>
          <linearGradient id="edge-magenta" x1="0" x2="1">
            <stop offset="0%" stopColor="#f0b366" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#f0b366" stopOpacity="0.8" />
          </linearGradient>
          <linearGradient id="edge-chartreuse" x1="0" x2="1">
            <stop offset="0%" stopColor="#f0b366" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#5cf2c7" stopOpacity="0.85" />
          </linearGradient>
        </defs>

        {/* dot grid */}
        <rect x="0" y="0" width={W} height={H} fill="url(#dots)" />

        {/* Edges */}
        {EDGES.map(([from, to], i) => {
          const a = NODE_BY_NAME[from];
          const b = NODE_BY_NAME[to];
          const fromState = nodeStates[from];
          const toState = nodeStates[to];
          const active = fromState === "done" && toState === "running";
          const flowing = fromState === "running" || active;
          const done = fromState === "done" && (toState === "done" || toState === "skipped");
          const targetTone = TONE_COLOR[b.tone];

          // Curved path
          const dy = b.y - a.y;
          const mx = (a.x + b.x) / 2;
          const my = (a.y + b.y) / 2 - Math.abs(dy) * 0.12;

          const stroke = active
            ? `url(#edge-${b.tone})`
            : done
              ? "rgba(52, 211, 153, 0.45)"
              : "var(--color-line-2)";
          const strokeWidth = active ? 1.8 : 1;
          const dash = active ? "5 4" : done ? undefined : "2 4";

          // Particle along path
          const particleProgress = (t / 2400 + i * 0.13) % 1;
          const pX = a.x + (b.x - a.x) * particleProgress;
          // approximate Y on quadratic curve
          const pT = particleProgress;
          const pY =
            (1 - pT) * (1 - pT) * a.y +
            2 * (1 - pT) * pT * my +
            pT * pT * b.y;

          return (
            <g key={`${from}-${to}-${i}`}>
              <path
                d={`M ${a.x} ${a.y} Q ${mx} ${my}, ${b.x} ${b.y}`}
                fill="none"
                stroke={stroke}
                strokeWidth={strokeWidth}
                strokeDasharray={dash}
                strokeLinecap="round"
                style={
                  active
                    ? {
                        animation: "flow-stream 1s linear infinite",
                        filter: `drop-shadow(0 0 6px ${targetTone})`,
                      }
                    : undefined
                }
                vectorEffect="non-scaling-stroke"
              />
              {flowing && (
                <circle
                  cx={pX}
                  cy={pY}
                  r={2.6}
                  fill={targetTone}
                  style={{ filter: `drop-shadow(0 0 6px ${targetTone})` }}
                />
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {NODES.map((node) => {
          const status = nodeStates[node.name];
          const tone = TONE_COLOR[node.tone];
          const color =
            status === "running"
              ? tone
              : status === "done"
                ? STATUS_COLOR.done
                : status === "failed"
                  ? STATUS_COLOR.failed
                  : status === "pending"
                    ? STATUS_COLOR.pending
                    : STATUS_COLOR.skipped;
          const isRunning = status === "running";
          const isDone = status === "done";
          const isPending = status === "pending";
          return (
            <motion.g
              key={node.name}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.45, ease: [0.19, 1, 0.22, 1] }}
            >
              {/* Halo when running */}
              {isRunning && (
                <motion.circle
                  cx={node.x}
                  cy={node.y}
                  r={28}
                  fill="none"
                  stroke={color}
                  strokeWidth={1}
                  animate={{ r: [22, 36, 22], opacity: [0.55, 0, 0.55] }}
                  transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                />
              )}

              {/* Background fill */}
              <rect
                x={node.x - 56}
                y={node.y - 22}
                width={112}
                height={44}
                rx={8}
                fill="var(--color-panel)"
                stroke={color}
                strokeWidth={isPending ? 1 : 1.5}
                style={{
                  filter:
                    isRunning || isDone
                      ? `drop-shadow(0 0 8px ${color})`
                      : undefined,
                }}
              />

              {/* Status dot */}
              <circle
                cx={node.x - 44}
                cy={node.y}
                r={3}
                fill={color}
                style={{ filter: `drop-shadow(0 0 4px ${color})` }}
              />

              {/* Label */}
              <text
                x={node.x - 36}
                y={node.y - 3}
                textAnchor="start"
                fontFamily="var(--font-mono)"
                fontSize="10.5"
                fontWeight="600"
                letterSpacing="0.08em"
                fill={isPending ? "var(--color-fg-mute)" : "var(--color-fg)"}
              >
                {node.label}
              </text>
              <text
                x={node.x - 36}
                y={node.y + 11}
                textAnchor="start"
                fontFamily="var(--font-mono)"
                fontSize="9"
                fill={isPending ? "var(--color-fg-faint)" : "var(--color-fg-mute)"}
              >
                {node.sub}
              </text>

              {/* Status ribbon */}
              <text
                x={node.x}
                y={node.y + 36}
                textAnchor="middle"
                fontFamily="var(--font-mono)"
                fontSize="8.5"
                letterSpacing="0.18em"
                fill={color}
                opacity={isPending ? 0.5 : 1}
              >
                {status.toUpperCase()}
              </text>
            </motion.g>
          );
        })}

        {/* Decorative quadrant markers */}
        <text x="20" y="28" fontFamily="var(--font-mono)" fontSize="9" fill="var(--color-fg-faint)" letterSpacing="0.18em">
          §01 · INPUT
        </text>
        <text x={W - 130} y="28" fontFamily="var(--font-mono)" fontSize="9" fill="var(--color-fg-faint)" letterSpacing="0.18em">
          §05 · OUTPUT
        </text>
        <text x={W / 2 - 60} y={H - 14} fontFamily="var(--font-mono)" fontSize="9" fill="var(--color-fg-faint)" letterSpacing="0.18em">
          §03 · PARALLEL FAN-OUT
        </text>
      </svg>
    </div>
  );
}
