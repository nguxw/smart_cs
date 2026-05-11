import { useCallback, useMemo, useState } from "react";

import type {
  ActionPlan,
  AgentStep,
  CaseTask,
  ChatMessage,
  Citation,
  ConversationSnapshot,
  PendingConfirmation,
  StreamState,
  SupportCase,
  ToolCall
} from "../types/api";
import { API_BASE, fetchJson } from "../services/apiClient";
import { confirmTask } from "../services/casesApi";
import { streamChat } from "../services/chatStream";

export function useChatStream(userId: string, onAfterMutation?: () => Promise<void>) {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [actionPlan, setActionPlan] = useState<ActionPlan | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [currentCase, setCurrentCase] = useState<SupportCase | null>(null);
  const [currentTask, setCurrentTask] = useState<CaseTask | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingConfirmation | null>(null);
  const [conversationSnapshot, setConversationSnapshot] =
    useState<ConversationSnapshot | null>(null);
  const [streamState, setStreamState] = useState<StreamState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const latestIntent = useMemo(() => {
    const router = [...agentSteps].reverse().find((step) => step.agent === "router");
    return router?.message.replace(/^intent=/, "") ?? "idle";
  }, [agentSteps]);

  const latestGuardrail = useMemo(() => {
    const step = [...agentSteps].reverse().find((item) => item.agent === "guardrail");
    return step?.message ?? "ready";
  }, [agentSteps]);

  const agentLatency = useMemo(
    () => Math.round(agentSteps.reduce((sum, step) => sum + (step.elapsed_ms ?? 0), 0)),
    [agentSteps]
  );

  const loadConversation = useCallback(async (
    nextConversationId: string,
    options?: { preserveRunArtifacts?: boolean }
  ) => {
    const [snapshot, state] = await Promise.all([
      fetchJson<ConversationSnapshot>(`${API_BASE}/api/conversations/${nextConversationId}`),
      fetchJson<StreamState>(`${API_BASE}/api/conversations/${nextConversationId}/stream-state`)
    ]);
    const latestCase = [...(snapshot.cases ?? [])].sort((left, right) =>
      right.updated_at.localeCompare(left.updated_at)
    )[0] ?? null;
    const latestTask = [...(snapshot.tasks ?? [])].sort((left, right) =>
      right.updated_at.localeCompare(left.updated_at)
    )[0] ?? null;
    setConversationId(nextConversationId);
    setConversationSnapshot(snapshot);
    setStreamState(state);
    setMessages(
      snapshot.messages
        .filter((message): message is ChatMessage =>
          message.role === "user" || message.role === "assistant"
        )
        .map((message) => ({ role: message.role, content: message.content }))
    );
    if (!options?.preserveRunArtifacts) {
      setAgentSteps(snapshot.agent_steps ?? []);
      setToolCalls(snapshot.tool_calls ?? []);
    }
    setCurrentCase(latestCase);
    setCurrentTask(latestTask);
  }, []);

  const send = useCallback(
    async (message: string) => {
      if (!message.trim() || busy) return;
      setError(null);
      setBusy(true);
      setMessages((current) => [
        ...current,
        { role: "user", content: message },
        { role: "assistant", content: "" }
      ]);
      setAgentSteps([]);
      setActionPlan(null);
      setCitations([]);
      setToolCalls([]);
      setPendingConfirmation(null);
      try {
        await streamChat(message, userId, conversationId, {
          onToken: (content) => {
            setMessages((current) => {
              const next = [...current];
              const last = next[next.length - 1];
              if (last?.role === "assistant") {
                next[next.length - 1] = { ...last, content: `${last.content}${content}` };
              }
              return next;
            });
          },
          onAgentStep: (step) => setAgentSteps((current) => [...current, step]),
          onActionPlan: (plan) => setActionPlan(plan),
          onCitation: (doc) =>
            setCitations((current) =>
              current.some((item) => item.id === doc.id) ? current : [...current, doc]
            ),
          onToolCall: (call) => setToolCalls((current) => [...current, call]),
          onCaseUpdate: (supportCase) => setCurrentCase(supportCase),
          onTaskUpdate: (task) => setCurrentTask(task),
          onActionRequired: (payload) => {
            setPendingConfirmation(payload.pending_confirmation ?? null);
          },
          onFinal: (payload) => {
            setActionPlan(payload.action_plan ?? null);
            setConversationId(payload.conversation_id);
            window.setTimeout(
              () => void loadConversation(payload.conversation_id, { preserveRunArtifacts: true }),
              180
            );
          },
          onError: (messageText) => setError(messageText)
        });
        try {
          await onAfterMutation?.();
        } catch (cause) {
          console.warn("Post-chat refresh failed", cause);
        }
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Chat request failed");
      } finally {
        setBusy(false);
      }
    },
    [busy, conversationId, loadConversation, onAfterMutation, userId]
  );

  const approveTask = useCallback(
    async (approved: boolean) => {
      const taskId = currentTask?.id ?? pendingConfirmation?.task_id;
      if (!taskId) return null;
      const response = await confirmTask(taskId, userId, approved);
      const nextConversationId = conversationId ?? currentCase?.conversation_id ?? null;
      await Promise.all([
        nextConversationId ? loadConversation(nextConversationId) : Promise.resolve(),
        onAfterMutation?.() ?? Promise.resolve()
      ]);
      setPendingConfirmation(null);
      return response;
    },
    [
      conversationId,
      currentCase?.conversation_id,
      currentTask,
      loadConversation,
      onAfterMutation,
      pendingConfirmation,
      userId
    ]
  );

  const reset = useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setAgentSteps([]);
    setActionPlan(null);
    setCitations([]);
    setToolCalls([]);
    setCurrentCase(null);
    setCurrentTask(null);
    setPendingConfirmation(null);
    setConversationSnapshot(null);
    setStreamState(null);
    setError(null);
  }, []);

  return {
    conversationId,
    messages,
    agentSteps,
    actionPlan,
    citations,
    toolCalls,
    currentCase,
    currentTask,
    pendingConfirmation,
    conversationSnapshot,
    streamState,
    busy,
    error,
    latestIntent,
    latestGuardrail,
    agentLatency,
    send,
    approveTask,
    loadConversation,
    reset
  };
}
