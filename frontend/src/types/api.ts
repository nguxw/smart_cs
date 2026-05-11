import type { ReactNode } from "react";

export type ChatRole = "user" | "assistant";

export type AgentStep = {
  agent: string;
  status: string;
  message: string;
  elapsed_ms?: number;
};

export type ActionPlan = {
  intent: string;
  confidence: number;
  slots?: Record<string, unknown>;
  required_tools?: string[];
  missing_slots?: string[];
  risk_level?: "low" | "medium" | "high";
  requires_confirmation?: boolean;
  requires_handoff?: boolean;
  reason?: string;
};

export type Citation = {
  id: string;
  title: string;
  content: string;
  source: string;
  category: string;
  tags?: string[];
  score?: number;
  version?: number;
  status?: string;
  grounding_score?: number;
};

export type ToolCall = {
  name: string;
  arguments?: Record<string, unknown>;
  success: boolean;
  result?: unknown;
  error?: string | null;
  duration_ms?: number;
  audit_id?: string | null;
  policy_status?: string;
  idempotency_key?: string | null;
  requires_confirmation?: boolean;
};

export type Ticket = {
  id: string;
  user_id: string;
  title: string;
  description?: string;
  status: string;
  priority: string;
  category: string;
  assigned_to?: string | null;
  assignee_name?: string | null;
  sla_deadline?: string | null;
  handoff_reason?: string;
  agent_summary?: string;
  customer_emotion?: string;
  latest_customer_message?: string;
  suggested_reply?: string;
  human_reply?: string;
  resolution_type?: string;
  closed_reason?: string;
  csat_score?: number | null;
  created_at: string;
  updated_at?: string;
};

export type TicketThread = {
  ticket: Ticket;
  case?: SupportCase | null;
  conversation?: ConversationSnapshot | null;
};

export type SupportCase = {
  id: string;
  user_id: string;
  tenant_id: string;
  conversation_id: string;
  category: string;
  status: string;
  priority: string;
  source_channel: string;
  related_order_id?: string | null;
  related_ticket_id?: string | null;
  current_task_id?: string | null;
  resolution?: string;
  risk_level?: string;
  summary?: string;
  created_at: string;
  updated_at: string;
};

export type CaseTask = {
  id: string;
  case_id: string;
  type: string;
  status: string;
  required_action: string;
  pending_confirmation?: Record<string, unknown> | null;
  assigned_to?: string | null;
  deadline?: string | null;
  result?: Record<string, unknown> | null;
  resume_token: string;
  created_at: string;
  updated_at: string;
};

export type ToolAudit = {
  id: string;
  conversation_id: string;
  case_id?: string | null;
  task_id?: string | null;
  tool_name: string;
  arguments: Record<string, unknown>;
  auth_context: Record<string, unknown>;
  policy_status: string;
  success: boolean;
  result?: unknown;
  error?: string | null;
  idempotency_key?: string | null;
  requires_confirmation: boolean;
  created_at: string;
};

export type EvalRun = {
  id: string;
  metrics: Record<string, number | string | Record<string, number>>;
  cases?: Array<Record<string, unknown>>;
  markdown_report: string;
};

export type Health = {
  status: string;
  llm_provider: string;
  llm_model: string;
  qdrant_collection: string;
  repository_backend: string;
  runtime_backend: string;
  knowledge_backend: string;
};

export type ToolSpec = {
  name: string;
  description?: string;
  category?: string;
  inputSchema?: unknown;
};

export type GraphEdge =
  | { source: string; target: string; condition?: string }
  | [string, string]
  | string;

export type GraphMetadata = {
  nodes?: string[];
  edges?: GraphEdge[];
  interrupt_nodes?: string[];
  checkpoint_fields?: string[];
  langgraph_available?: boolean;
  execution_mode?: string;
  langgraph_runtime?: string;
  langgraph_nodes_bound?: boolean;
};

export type HarnessPlane = {
  id: string;
  title: string;
  purpose: string;
  evidence: string[];
};

export type HarnessManifest = {
  name: string;
  version: string;
  definition: string;
  agent_state_contract: string[];
  event_contract: Record<string, unknown>;
  planes: HarnessPlane[];
  release_gates: Record<string, number>;
  change_policy: string[];
};

export type ConversationMessage = {
  role: ChatRole | string;
  content: string;
  created_at?: string;
};

export type ConversationSnapshot = {
  id: string;
  user_id: string;
  summary: string;
  messages: ConversationMessage[];
  agent_steps: AgentStep[];
  tool_calls: ToolCall[];
  trace_ids: string[];
  cases?: SupportCase[];
  tasks?: CaseTask[];
  updated_at: string;
};

export type StreamState = {
  conversation_id: string;
  short_memory: ConversationMessage[];
  stream_events: Array<{ id?: string; event?: string; data?: unknown; timestamp?: number }>;
};

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type PendingConfirmation = {
  tool?: string;
  arguments?: Record<string, unknown>;
  summary?: string;
  risk_level?: string;
  mode?: string;
  estimated_effect?: string;
  requires_confirmation?: boolean;
  task_id?: string;
  idempotency_key?: string;
};

export type StreamFinal = {
  conversation_id: string;
  trace_id: string;
  case_id?: string | null;
  task_id?: string | null;
  action_required?: string | null;
  pending_confirmation?: PendingConfirmation | null;
  resume_token?: string | null;
  intent?: string;
  action_plan?: ActionPlan | null;
  graph_path?: string[];
};

export type TabKey = "desk" | "cases" | "tickets" | "kb" | "evals" | "system";

export type NavItem = {
  key: TabKey;
  label: string;
  icon: ReactNode;
};
