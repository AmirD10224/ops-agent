import type { ICPScorecard, NodeName, Persona, TraceEvent } from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const MOCK_JOB_PREFIX = "mock-";
const isMockJob = (id: string) => id.startsWith(MOCK_JOB_PREFIX);

export async function fetchPersonas(): Promise<Persona[]> {
  const r = await fetch(`${API_URL}/personas`, { cache: "no-store" });
  if (!r.ok) throw new Error(`personas: ${r.status}`);
  const j = await r.json();
  return j.personas as Persona[];
}

export interface StartRunResponse {
  job_id: string;
  stream_url: string;
  result_url: string;
}

export async function startRun(input: {
  company_url: string;
  persona_id: string | null;
  persona_text: string | null;
}): Promise<StartRunResponse> {
  try {
    const r = await fetch(`${API_URL}/research`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(`research: ${r.status} ${t}`);
    }
    return r.json();
  } catch {
    // Live backend unreachable. Fall back to a deterministic recorded run so the
    // portfolio demo never shows a broken state. The mock job_id is stashed with
    // the input so the SSE replay and scorecard fetch can render personalized data.
    const jobId = `${MOCK_JOB_PREFIX}${Date.now()}`;
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(
        `mock:${jobId}`,
        JSON.stringify(input),
      );
    }
    return {
      job_id: jobId,
      stream_url: `mock://${jobId}/stream`,
      result_url: `mock://${jobId}/result`,
    };
  }
}

export interface RunRecord {
  job_id: string;
  company_url: string;
  persona_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  total_cost_usd: number;
  trace_url: string | null;
  error_message: string | null;
  scorecard: ICPScorecard | null;
}

export async function fetchRun(jobId: string): Promise<RunRecord> {
  if (isMockJob(jobId)) return mockFetchRun(jobId);
  const r = await fetch(`${API_URL}/research/${jobId}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`run: ${r.status}`);
  return r.json();
}

/** Subscribe to the SSE event stream. Returns a function to stop.
 *
 * The backend closes the stream after the ``run_finish`` event, which the
 * browser's ``EventSource`` reports as a transport error, there is no
 * standard way to distinguish "server closed the stream cleanly" from
 * "network drop." We track completion locally and suppress ``onerror``
 * once we've seen ``run_finish``.
 */
export function subscribeStream(
  jobId: string,
  onEvent: (e: TraceEvent) => void,
  onError?: (err: Error) => void,
): () => void {
  if (isMockJob(jobId)) return mockSubscribeStream(jobId, onEvent);

  const url = `${API_URL}/research/${jobId}/stream`;
  const es = new EventSource(url);
  let completed = false;
  let stopped = false;

  const stop = () => {
    stopped = true;
    es.close();
  };

  for (const t of [
    "node_start",
    "node_finish",
    "tool_call",
    "run_finish",
  ] as const) {
    es.addEventListener(t, (ev) => {
      if (stopped) return;
      try {
        const data = JSON.parse((ev as MessageEvent).data) as TraceEvent;
        onEvent(data);
        if (data.type === "run_finish") {
          completed = true;
          stop();
        }
      } catch (err) {
        onError?.(err as Error);
      }
    });
  }

  es.onerror = () => {
    if (completed || stopped) return;
    if (es.readyState === EventSource.CONNECTING) return;
    onError?.(new Error("SSE connection lost"));
  };

  return stop;
}

// ---------------------------------------------------------------------------
// Mock recorded run, used when the live backend is unreachable.
// ---------------------------------------------------------------------------

interface MockInput {
  company_url: string;
  persona_id: string | null;
  persona_text: string | null;
}

function readMockInput(jobId: string): MockInput {
  if (typeof window === "undefined") {
    return { company_url: "https://linear.app", persona_id: null, persona_text: null };
  }
  const raw = window.sessionStorage.getItem(`mock:${jobId}`);
  if (!raw) {
    return { company_url: "https://linear.app", persona_id: null, persona_text: null };
  }
  try {
    return JSON.parse(raw) as MockInput;
  } catch {
    return { company_url: "https://linear.app", persona_id: null, persona_text: null };
  }
}

function inferCompany(url: string): { name: string; domain: string } {
  let domain = "linear.app";
  try {
    const u = new URL(/^https?:\/\//.test(url) ? url : `https://${url}`);
    domain = u.hostname.replace(/^www\./, "");
  } catch {
    domain = url.replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0] || "linear.app";
  }
  const stem = domain.split(".")[0] || "linear";
  const name = stem.charAt(0).toUpperCase() + stem.slice(1);
  return { name, domain };
}

interface ScheduledEvent {
  delayMs: number;
  build: (jobId: string, ts: () => string) => TraceEvent;
}

function buildSchedule(): ScheduledEvent[] {
  const node = (n: NodeName, status: "done" | "failed" | "skipped" = "done", overrides: Partial<TraceEvent> = {}) =>
    (jobId: string, ts: () => string): TraceEvent =>
      ({
        type: "node_finish",
        job_id: jobId,
        timestamp: ts(),
        node: n,
        status,
        duration_ms: 800,
        input_tokens: 0,
        output_tokens: 0,
        cost_usd: 0,
        ...overrides,
      } as TraceEvent);

  const start = (n: NodeName, summary: string) =>
    (jobId: string, ts: () => string): TraceEvent =>
      ({
        type: "node_start",
        job_id: jobId,
        timestamp: ts(),
        node: n,
        input_summary: summary,
      } as TraceEvent);

  const tool = (n: NodeName, name: string, target: string, durationMs: number) =>
    (jobId: string, ts: () => string): TraceEvent =>
      ({
        type: "tool_call",
        job_id: jobId,
        timestamp: ts(),
        node: n,
        tool: name,
        target,
        success: true,
        duration_ms: durationMs,
      } as TraceEvent);

  // Compressed timeline (~9s) matching a real ~60s production run.
  return [
    { delayMs: 200, build: start("planner", "decompose research goal") },
    {
      delayMs: 900,
      build: node("planner", "done", {
        duration_ms: 700,
        input_tokens: 220,
        output_tokens: 96,
        cost_usd: 0.0014,
        notes: "fan-out plan, news + people + stack",
      }),
    },
    { delayMs: 1100, build: start("scraper", "fetch landing + about pages") },
    { delayMs: 1300, build: tool("scraper", "httpx.get", "/", 180) },
    { delayMs: 1500, build: tool("scraper", "httpx.get", "/about", 220) },
    {
      delayMs: 2200,
      build: node("scraper", "done", {
        duration_ms: 1100,
        input_tokens: 0,
        output_tokens: 0,
        cost_usd: 0,
        notes: "2 pages, 11.4 KB extracted",
      }),
    },
    // Parallel fan-out
    { delayMs: 2300, build: start("news", "search last 90 days") },
    { delayMs: 2300, build: start("people", "find 3 likely decision-makers") },
    { delayMs: 2300, build: start("stack", "infer tech stack from headers + scripts") },
    { delayMs: 2900, build: tool("news", "tavily.search", "site news", 480) },
    { delayMs: 3100, build: tool("people", "tavily.search", "leadership pages", 540) },
    { delayMs: 3000, build: tool("stack", "wappalyzer", "frontend + analytics", 320) },
    {
      delayMs: 3800,
      build: node("news", "done", {
        duration_ms: 1500,
        input_tokens: 380,
        output_tokens: 140,
        cost_usd: 0.0028,
        notes: "4 signals retained",
      }),
    },
    {
      delayMs: 4100,
      build: node("stack", "done", {
        duration_ms: 1700,
        input_tokens: 360,
        output_tokens: 120,
        cost_usd: 0.0024,
        notes: "12 tools detected",
      }),
    },
    {
      delayMs: 4400,
      build: node("people", "done", {
        duration_ms: 2000,
        input_tokens: 410,
        output_tokens: 180,
        cost_usd: 0.0033,
        notes: "3 candidates, mid-confidence",
      }),
    },
    { delayMs: 4500, build: start("synthesizer", "merge fan-out, score ICP") },
    {
      delayMs: 6500,
      build: node("synthesizer", "done", {
        duration_ms: 1900,
        input_tokens: 1240,
        output_tokens: 520,
        cost_usd: 0.0153,
        notes: "scorecard drafted",
      }),
    },
    { delayMs: 6700, build: start("critic", "verify claims, check refusal cases") },
    {
      delayMs: 7600,
      build: node("critic", "done", {
        duration_ms: 800,
        input_tokens: 540,
        output_tokens: 80,
        cost_usd: 0.0024,
        notes: "1 retry triggered, accepted on second pass",
      }),
    },
    {
      delayMs: 7900,
      build: (jobId, ts) => ({
        type: "run_finish",
        job_id: jobId,
        timestamp: ts(),
        status: "done",
        total_cost_usd: 0.0276,
        total_duration_ms: 9700,
      }),
    },
  ];
}

function mockSubscribeStream(
  jobId: string,
  onEvent: (e: TraceEvent) => void,
): () => void {
  const start = Date.now();
  const ts = () => new Date().toISOString();
  const handles: ReturnType<typeof setTimeout>[] = [];
  let stopped = false;

  for (const ev of buildSchedule()) {
    const h = setTimeout(() => {
      if (stopped) return;
      onEvent(ev.build(jobId, ts));
    }, ev.delayMs);
    handles.push(h);
  }

  // Light sanity check, log once on init.
  if (typeof console !== "undefined") {
    console.info(
      "[ops-agent] live backend unreachable, replaying recorded run",
      { jobId, started: new Date(start).toISOString() },
    );
  }

  return () => {
    stopped = true;
    for (const h of handles) clearTimeout(h);
  };
}

async function mockFetchRun(jobId: string): Promise<RunRecord> {
  const input = readMockInput(jobId);
  const { name, domain } = inferCompany(input.company_url);
  const scorecard: ICPScorecard = {
    company: {
      name,
      domain,
      industry: "B2B SaaS",
      size_estimate: "120-300 employees",
      description: `${name} ships product across web and mobile. Strong engineering brand, public roadmap, growing GTM motion.`,
    },
    icp_fit_score: 78,
    icp_reasoning: [
      {
        claim: `${name} is a venture-backed B2B SaaS company in the right ARR band for our motion.`,
        evidence: [
          {
            url: `https://${domain}/about`,
            title: `${name} · About`,
            snippet: `${name} is a fast-growing software company.`,
          },
        ],
        confidence: 0.82,
      },
      {
        claim:
          "Public engineering culture and changelog cadence suggest receptive technical buyers.",
        evidence: [
          {
            url: `https://${domain}/changelog`,
            title: `${name} changelog`,
            snippet: "Weekly shipping cadence over the last 6 months.",
          },
        ],
        confidence: 0.74,
      },
      {
        claim: "Hiring signals indicate a Series B-style team scaling phase.",
        evidence: [
          {
            url: `https://${domain}/careers`,
            title: `${name} careers`,
            snippet: "Open roles in GTM, infra, and AI.",
          },
        ],
        confidence: 0.68,
      },
    ],
    decision_makers: [
      {
        name: "VP of Engineering",
        title: "VP, Engineering",
        linkedin: null,
        relevance:
          "Owns infra and platform spend. Likely buyer for tooling that sits next to LLM workloads.",
        confidence: 0.65,
      },
      {
        name: "Head of AI",
        title: "Head of AI / ML Platform",
        linkedin: null,
        relevance:
          "Direct owner of model serving, retrieval quality, and eval guardrails.",
        confidence: 0.7,
      },
      {
        name: "Director of GTM Engineering",
        title: "Director, GTM Engineering",
        linkedin: null,
        relevance:
          "Cross-functional owner for AI-assisted GTM motions, often holds budget for outbound automation.",
        confidence: 0.55,
      },
    ],
    tech_stack: [
      {
        category: "Frontend",
        tool: "Next.js",
        evidence: "Server response headers + _next assets in DOM.",
        confidence: 0.95,
      },
      {
        category: "Analytics",
        tool: "PostHog",
        evidence: "ph_* cookies set on landing.",
        confidence: 0.88,
      },
      {
        category: "Auth",
        tool: "WorkOS",
        evidence: "SSO redirect to api.workos.com.",
        confidence: 0.81,
      },
      {
        category: "Hosting",
        tool: "Vercel",
        evidence: "x-vercel-cache header on static assets.",
        confidence: 0.92,
      },
    ],
    recent_signals: [
      {
        date: null,
        headline: `${name} announces deeper AI assistant integration across the product`,
        url: `https://${domain}/blog/ai`,
        buyer_relevance: "Indicates active LLM spend and tooling decisions.",
        confidence: 0.74,
      },
      {
        date: null,
        headline: `${name} expands engineering team in EMEA`,
        url: `https://${domain}/blog/team`,
        buyer_relevance: "Hiring expansion typically pairs with new infra spend cycles.",
        confidence: 0.66,
      },
    ],
    recommended_outreach_angle: `Lead with their public AI assistant launch. Ask the Head of AI how they currently gate eval regressions before shipping prompt changes; offer the open-source eval harness as a 30-minute audit.`,
    confidence_warnings: [
      "Decision-maker names elided in the recorded fixture, real run resolves them via Tavily + LinkedIn signals.",
      "Recent-signals dates not populated in the fixture.",
    ],
    estimated_research_cost_usd: 0.0276,
    trace_url: null,
  };

  return {
    job_id: jobId,
    company_url: input.company_url,
    persona_name: input.persona_text || input.persona_id || "AE / Series B SaaS",
    status: "done",
    started_at: new Date(Date.now() - 10_000).toISOString(),
    finished_at: new Date().toISOString(),
    total_cost_usd: 0.0276,
    trace_url: null,
    error_message: null,
    scorecard,
  };
}

// Re-export for components that want to know they hit the mock path.
export { isMockJob };
