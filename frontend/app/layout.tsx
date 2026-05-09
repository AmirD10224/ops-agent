import "./globals.css";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";

export const metadata: Metadata = {
  title: "OpsAgent. Multi-step research agent",
  description:
    "A LangGraph research agent. Scores ICP fit, names decision-makers, infers stack, drafts an outreach angle, every node, tool call, token, and dollar streamed live.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable}`}
    >
      <body>
        <div className="min-h-screen flex flex-col">
          {/* Top status bar */}
          <header className="sticky top-0 z-30 border-b border-[var(--color-line)] bg-[var(--color-bg)]/85 backdrop-blur-md">
            <div className="max-w-[1320px] mx-auto px-5 h-11 flex items-center gap-5 text-[11.5px]">
              <Link href="/" className="flex items-center gap-2.5">
                <Image src="/logo.svg" alt="ops-agent" width={30} height={20} priority className="h-5 w-auto" />
                <span className="font-semibold tracking-tight uppercase text-[var(--color-fg)]">
                  OpsAgent
                </span>
                <span className="text-[var(--color-fg-faint)]">/</span>
                <span className="text-[var(--color-fg-mute)] uppercase tracking-tight">
                  Research surface
                </span>
              </Link>

              <span className="h-4 w-px bg-[var(--color-line-2)]" />

              <span className="flex items-center gap-1.5">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-emerald)] pulse shadow-[0_0_8px_var(--color-emerald)]" />
                <span className="text-[var(--color-emerald)] glow-emerald font-medium">ONLINE</span>
              </span>

              <span className="h-4 w-px bg-[var(--color-line-2)]" />

              <span className="text-[var(--color-fg-mute)] uppercase tracking-tight hidden md:inline tabular">
                LangGraph 0.2 · 7 nodes · Anthropic + Tavily
              </span>

              <nav className="ml-auto flex items-center gap-1">
                <ExampleLink href="/example/linear" name="Linear" tone="cyan" />
                <ExampleLink href="/example/faire" name="Faire" tone="violet" />
                <ExampleLink href="/example/allbirds" name="Allbirds" tone="magenta" />
                <a
                  className="ml-2 inline-flex items-center px-3 py-1 text-[11px] border border-[var(--color-cyan)] text-[var(--color-cyan)] hover:bg-[var(--color-cyan)] hover:text-[var(--color-bg)] transition-colors label-mono rounded-sm"
                  href="https://github.com/AmirD10224/ops-agent"
                  target="_blank"
                  rel="noreferrer"
                >
                  Source
                </a>
              </nav>
            </div>
          </header>

          <main className="flex-1 max-w-[1320px] mx-auto w-full px-5 py-8">
            {children}
          </main>

          <footer className="border-t border-[var(--color-line)] bg-[var(--color-panel)] mt-12">
            <div className="max-w-[1320px] mx-auto px-5 h-9 flex items-center gap-4 text-[11px] text-[var(--color-fg-mute)]">
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-cyan)] pulse shadow-[0_0_6px_var(--color-cyan)]" />
                <span className="text-[var(--color-cyan)]">Connected</span>
                <span className="text-[var(--color-fg-mute)]">· /v1/research</span>
              </span>
              <span className="h-4 w-px bg-[var(--color-line-2)]" />
              <span>Heartbeat · 1.0s</span>
              <span className="h-4 w-px bg-[var(--color-line-2)]" />
              <span className="hidden md:inline tabular">
                LangGraph 0.2 · Sonnet 4.6 + Haiku 4.5 · Tavily · Modal · Langfuse
              </span>
              <span className="ml-auto tabular">v0.1.0 · build adc1842</span>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}

function ExampleLink({
  href,
  name,
  tone,
}: {
  href: string;
  name: string;
  tone: "cyan" | "violet" | "magenta";
}) {
  const dot = {
    cyan: "var(--color-cyan)",
    violet: "var(--color-violet)",
    magenta: "var(--color-magenta)",
  }[tone];
  return (
    <Link
      href={href as never}
      className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-[var(--color-fg-dim)] hover:text-[var(--color-fg)] transition-colors label-mono text-[11px] rounded-sm hover:bg-[oklch(100%_0_0/0.04)]"
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: dot, boxShadow: `0 0 6px ${dot}` }}
      />
      {name}
    </Link>
  );
}
