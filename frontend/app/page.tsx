import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { fetchPersonas } from "@/lib/api";
import type { Persona } from "@/lib/types";
import { RunPanel } from "@/components/RunPanel";

const FALLBACK_PERSONAS: Persona[] = [
  {
    id: "ae_series_b_saas",
    name: "AE / Series B SaaS",
    description:
      "Account executive selling a $50–250k ACV B2B SaaS product to RevOps and Sales leadership.",
  },
  {
    id: "revops_plg",
    name: "RevOps Director / PLG",
    description: "Head of RevOps at a product-led B2B SaaS company.",
  },
  {
    id: "sdr_seed_founder",
    name: "Founder/SDR / Seed B2B",
    description: "Seed-stage founder running outbound personally.",
  },
];

export const dynamic = "force-dynamic";

export default async function Home() {
  let personas: Persona[] = FALLBACK_PERSONAS;
  try {
    personas = await fetchPersonas();
  } catch {
    // API unreachable at SSR, fall back to baked-in list. Static demo still renders.
  }

  return (
    <div className="space-y-8">
      {/* HERO STRIP */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-4 fade-up">
        {/* Headline panel */}
        <div className="lg:col-span-8 panel panel-glow-cyan relative overflow-hidden">
          <div
            aria-hidden
            className="absolute -top-20 -right-20 h-72 w-72 rounded-full blur-3xl opacity-25"
            style={{
              background:
                "conic-gradient(from 180deg, var(--color-cyan), var(--color-violet), var(--color-magenta), var(--color-cyan))",
            }}
          />
          <div className="panel-header">
            <span>v0.1.0</span>
            <span className="ml-auto stamp stamp-cyan">LangGraph 0.2</span>
          </div>
          <div className="p-7 md:p-9">
            <p className="eyebrow mb-5">B2B research agent</p>
            <h1
              className="display text-balance text-[var(--color-fg)]"
              style={{ fontSize: "clamp(40px, 6.5vw, 84px)" }}
            >
              Give it a company.
              <br />
              Get back an <span className="iris-text">ICP scorecard</span>.
            </h1>
            <p className="mt-7 max-w-2xl text-[15.5px] leading-[1.55] text-[var(--color-fg-dim)] font-sans">
              Paste a URL and pick a buyer persona. It scrapes the site,
              searches recent news, infers the tech stack, names a few likely
              decision-makers, scores ICP fit, and drafts an outreach angle.
              Seven nodes, every one of them stream their state to the UI as
              they run. Cost and latency per node land in Langfuse.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <a
                href="#dispatch"
                className="group inline-flex items-center gap-2 rounded-md px-5 py-2.5 text-[13px] font-semibold text-[var(--color-bg)] transition-[background-position,box-shadow] duration-500 shadow-[0_8px_24px_-8px_rgba(34,211,238,0.6)]"
                style={{
                  background:
                    "linear-gradient(90deg, var(--color-cyan) 0%, var(--color-violet) 50%, var(--color-cyan) 100%)",
                  backgroundSize: "200% 100%",
                }}
              >
                Dispatch agent
                <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
              </a>
              <Link
                href={"/example/linear" as never}
                className="inline-flex items-center gap-2 rounded-md px-5 py-2.5 text-[13px] font-medium border border-[var(--color-line-2)] text-[var(--color-fg)] hover:border-[var(--color-cyan)] hover:text-[var(--color-cyan)] transition-colors"
              >
                See a recorded run
              </Link>
            </div>
          </div>
        </div>

        {/* Spec stack */}
        <div className="lg:col-span-4 grid grid-rows-3 gap-4">
          <SpecCell n="07" label="Graph nodes" sub="planner → critic" tone="cyan" />
          <SpecCell n="25" label="Eval golden" sub="LLM-judge · κ ≥ 0.7" tone="violet" />
          <SpecCell n=".83" label="Mean score" sub="aggregate · 3-fixture" tone="chartreuse" />
        </div>
      </section>

      {/* RECORDED DEMOS */}
      <section>
        <header className="section-rule">
          <span className="section-rule__chip">§02</span>
          <span className="section-rule__title">Pre-recorded runs</span>
          <span className="section-rule__line" />
          <span className="text-[10.5px] font-mono text-[var(--color-fg-mute)] uppercase tracking-[0.16em]">
            no API key needed
          </span>
        </header>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <DemoLink id="linear" name="Linear" tag="Engineering-led SaaS" score="78" tone="cyan" />
          <DemoLink id="faire" name="Faire" tag="B2B marketplace" score="64" tone="violet" />
          <DemoLink id="allbirds" name="Allbirds" tag="DTC retail" score="42" tone="magenta" />
        </div>
      </section>

      {/* RUN PANEL */}
      <section id="dispatch">
        <header className="section-rule">
          <span className="section-rule__chip">§03</span>
          <span className="section-rule__title">Run it</span>
          <span className="section-rule__line" />
          <span className="text-[10.5px] font-mono text-[var(--color-fg-mute)] uppercase tracking-[0.16em]">
            ~60s, costs about $0.05
          </span>
        </header>
        <RunPanel personas={personas} />
      </section>
    </div>
  );
}

function SpecCell({
  n,
  label,
  sub,
  tone,
}: {
  n: string;
  label: string;
  sub: string;
  tone: "cyan" | "violet" | "chartreuse";
}) {
  const c = {
    cyan: "var(--color-cyan)",
    violet: "var(--color-violet-bright)",
    chartreuse: "var(--color-chartreuse-bright)",
  }[tone];
  const glow = {
    cyan: "glow-cyan",
    violet: "glow-violet",
    chartreuse: "glow-chartreuse",
  }[tone];
  return (
    <div className="panel relative overflow-hidden p-5">
      <div
        aria-hidden
        className="absolute -top-12 -right-12 h-32 w-32 rounded-full blur-3xl opacity-25"
        style={{ background: c }}
      />
      <div className="flex items-baseline justify-between gap-3">
        <p
          className={`display-mono ${glow}`}
          style={{ fontSize: 36, color: c, lineHeight: 0.9 }}
        >
          {n}
        </p>
        <span className="label-mono text-[10px] text-[var(--color-fg-mute)]">
          {label}
        </span>
      </div>
      <p className="mt-3 text-[10.5px] font-mono text-[var(--color-fg-mute)] uppercase tracking-tight">
        {sub}
      </p>
    </div>
  );
}

function DemoLink({
  id,
  name,
  tag,
  score,
  tone,
}: {
  id: string;
  name: string;
  tag: string;
  score: string;
  tone: "cyan" | "violet" | "magenta";
}) {
  const c = {
    cyan: "var(--color-cyan)",
    violet: "var(--color-violet-bright)",
    magenta: "var(--color-magenta-bright)",
  }[tone];
  const glow = {
    cyan: "glow-cyan",
    violet: "glow-violet",
    magenta: "glow-magenta",
  }[tone];
  const headerCls = {
    cyan: "panel-header",
    violet: "panel-header panel-header-violet",
    magenta: "panel-header panel-header-magenta",
  }[tone];
  return (
    <Link
      href={`/example/${id}` as never}
      className="group panel hover:border-[oklch(100%_0_0/0.15)] transition-colors block"
    >
      <div className={headerCls}>
        <span>Recorded · case</span>
        <span className="ml-auto tabular text-[var(--color-fg-faint)]">{id}</span>
      </div>
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p
              className="display text-[var(--color-fg)] text-[28px] leading-[1.05] group-hover:text-[var(--color-cyan)] transition-colors"
              style={{ color: undefined }}
            >
              {name}
            </p>
            <p className="mt-2 label-mono text-[10.5px] text-[var(--color-fg-mute)]">
              {tag}
            </p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-[9.5px] uppercase tracking-[0.16em] text-[var(--color-fg-mute)] mb-1">
              ICP
            </p>
            <p
              className={`display-mono ${glow} tabular`}
              style={{ fontSize: 32, color: c, lineHeight: 1 }}
            >
              {score}
            </p>
          </div>
        </div>
        <p className="mt-4 text-[11px] font-mono text-[var(--color-cyan)] flex items-center gap-1 group-hover:gap-2 transition-all">
          See briefing <ArrowRight className="size-3" />
        </p>
      </div>
    </Link>
  );
}
