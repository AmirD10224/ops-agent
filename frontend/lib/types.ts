// Shared types, keep aligned with backend Pydantic schemas.

export type NodeName =
  | "planner"
  | "scraper"
  | "news"
  | "people"
  | "stack"
  | "synthesizer"
  | "critic";

export type NodeStatus = "pending" | "running" | "done" | "failed" | "skipped";

export interface NodeStartEvent {
  type: "node_start";
  job_id: string;
  timestamp: string;
  node: NodeName;
  input_summary?: string;
}

export interface NodeFinishEvent {
  type: "node_finish";
  job_id: string;
  timestamp: string;
  node: NodeName;
  status: "done" | "failed" | "skipped";
  duration_ms: number;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
  error_message?: string | null;
  notes?: string;
}

export interface ToolCallEvent {
  type: "tool_call";
  job_id: string;
  timestamp: string;
  node: NodeName;
  tool: string;
  target: string;
  success: boolean;
  duration_ms: number;
  error_message?: string | null;
}

export interface RunFinishEvent {
  type: "run_finish";
  job_id: string;
  timestamp: string;
  status: "done" | "failed";
  total_cost_usd: number;
  total_duration_ms: number;
  trace_url?: string | null;
}

export type TraceEvent =
  | NodeStartEvent
  | NodeFinishEvent
  | ToolCallEvent
  | RunFinishEvent;

export interface Citation {
  url: string;
  title: string;
  snippet: string;
}

export interface ICPClaim {
  claim: string;
  evidence: Citation[];
  confidence: number;
}

export interface DecisionMaker {
  name: string;
  title: string;
  linkedin: string | null;
  relevance: string;
  confidence: number;
}

export interface StackEntry {
  category: string;
  tool: string;
  evidence: string;
  confidence: number;
}

export interface NewsSignal {
  date: string | null;
  headline: string;
  url: string;
  buyer_relevance: string;
  confidence: number;
}

export interface ICPScorecard {
  company: {
    name: string;
    domain: string;
    industry: string;
    size_estimate: string;
    description?: string;
  };
  icp_fit_score: number;
  icp_reasoning: ICPClaim[];
  decision_makers: DecisionMaker[];
  tech_stack: StackEntry[];
  recent_signals: NewsSignal[];
  recommended_outreach_angle: string;
  confidence_warnings: string[];
  estimated_research_cost_usd: number;
  trace_url?: string | null;
}

export interface Persona {
  id: string;
  name: string;
  description: string;
}

export const NODE_ORDER: NodeName[] = [
  "planner",
  "scraper",
  "news",
  "people",
  "stack",
  "synthesizer",
  "critic",
];
