import type {
  AgentStep,
  CaseTask,
  Citation,
  PendingConfirmation,
  StreamFinal,
  SupportCase,
  ToolCall
} from "../types/api";
import { API_BASE, authHeaders } from "./apiClient";

export type ChatStreamHandlers = {
  onToken: (content: string) => void;
  onAgentStep: (step: AgentStep) => void;
  onCitation: (doc: Citation) => void;
  onToolCall: (call: ToolCall) => void;
  onCaseUpdate: (supportCase: SupportCase) => void;
  onTaskUpdate: (task: CaseTask) => void;
  onActionRequired: (payload: {
    action_required?: string;
    pending_confirmation?: PendingConfirmation | null;
    case_id?: string | null;
    task_id?: string | null;
    resume_token?: string | null;
  }) => void;
  onFinal: (payload: StreamFinal) => void;
  onError: (message: string) => void;
};

export async function streamChat(
  message: string,
  userId: string,
  conversationId: string | null,
  handlers: ChatStreamHandlers
) {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(userId) },
    body: JSON.stringify({
      message,
      user_id: userId,
      conversation_id: conversationId
    })
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Chat request failed: ${response.status} ${detail}`);
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Streaming response is unavailable");

  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) handleFrame(frame, handlers);
  }
}

function handleFrame(frame: string, handlers: ChatStreamHandlers) {
  const event = frame
    .split("\n")
    .find((line) => line.startsWith("event:"))
    ?.replace("event:", "")
    .trim();
  const dataText = frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace("data:", "").trimStart())
    .join("\n");
  if (!event || !dataText) return;
  const data = JSON.parse(dataText);
  if (event === "agent_step" && data.status !== "started") handlers.onAgentStep(data);
  if (event === "citation") handlers.onCitation(data);
  if (event === "tool_call") handlers.onToolCall(data);
  if (event === "case_update") handlers.onCaseUpdate(data);
  if (event === "task_update") handlers.onTaskUpdate(data);
  if (event === "action_required") handlers.onActionRequired(data);
  if (event === "token") handlers.onToken(data.content ?? "");
  if (event === "final") handlers.onFinal(data);
  if (event === "error") handlers.onError(data.message ?? "Agent stream error");
}
