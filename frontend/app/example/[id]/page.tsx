import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { StaticExampleViewer } from "@/components/StaticExampleViewer";

const VALID_IDS = new Set(["linear", "faire", "allbirds"]);

export function generateStaticParams() {
  return Array.from(VALID_IDS).map((id) => ({ id }));
}

async function loadExample(id: string) {
  if (!VALID_IDS.has(id)) return null;
  const mod = await import(`@/public/examples/${id}.json`);
  return mod.default;
}

export default async function ExamplePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!VALID_IDS.has(id)) notFound();
  const data = await loadExample(id);
  if (!data) notFound();

  return (
    <div className="space-y-6">
      <header className="space-y-4 fade-up">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-[11px] font-mono text-[var(--color-fg-mute)] hover:text-[var(--color-cyan)] transition-colors uppercase tracking-[0.16em]"
        >
          <ArrowLeft className="size-3" />
          Back to dispatch
        </Link>

        <div className="panel panel-glow-violet relative overflow-hidden">
          <div
            aria-hidden
            className="absolute -top-20 -right-20 h-72 w-72 rounded-full blur-3xl opacity-20"
            style={{
              background:
                "conic-gradient(from 200deg, var(--color-violet), var(--color-magenta), var(--color-cyan), var(--color-violet))",
            }}
          />
          <div className="panel-header panel-header-violet">
            <span>Recorded briefing</span>
            <span className="ml-auto stamp stamp-violet tabular">{data.persona_name}</span>
          </div>
          <div className="p-6 md:p-8">
            <p className="eyebrow mb-4">▸ ~8s replay · compressed timeline · live Langfuse trace</p>
            <h1
              className="display text-balance text-[var(--color-fg)]"
              style={{ fontSize: "clamp(36px, 6vw, 76px)" }}
            >
              {data.scorecard.company.name}
              <span className="text-[var(--color-fg-faint)]">.</span>
            </h1>
            <p className="mt-3 text-[14px] leading-[1.55] text-[var(--color-fg-dim)] max-w-2xl font-sans">
              A real production run, captured at the time of execution and replayed
              here on a compressed timeline.
            </p>
          </div>
        </div>
      </header>

      <StaticExampleViewer data={data} />
    </div>
  );
}
