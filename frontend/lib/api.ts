import type { ICPScorecard, Persona, TraceEvent } from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    // Browsers report the readyState here; CONNECTING means auto-reconnect
    // is in progress and we should let it retry without surfacing an error.
    if (es.readyState === EventSource.CONNECTING) return;
    onError?.(new Error("SSE connection lost"));
  };

  return stop;
}
