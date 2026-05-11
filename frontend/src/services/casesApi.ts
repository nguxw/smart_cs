import type { CaseTask, SupportCase, ToolAudit } from "../types/api";
import { API_BASE, authHeaders, fetchJson } from "./apiClient";

export async function fetchCases() {
  const body = await fetchJson<{ cases: SupportCase[] }>(`${API_BASE}/api/cases`, {
    headers: authHeaders("agent-demo", "agent")
  });
  return body.cases ?? [];
}

export async function fetchCaseDetail(caseId: string) {
  return fetchJson<{
    case: SupportCase;
    tasks: CaseTask[];
    audits: ToolAudit[];
  }>(`${API_BASE}/api/cases/${caseId}`, {
    headers: authHeaders("agent-demo", "agent")
  });
}

export async function fetchTasks(status?: string) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const body = await fetchJson<{ tasks: CaseTask[] }>(`${API_BASE}/api/tasks${suffix}`, {
    headers: authHeaders("agent-demo", "agent")
  });
  return body.tasks ?? [];
}

export async function confirmTask(taskId: string, userId: string, approved = true) {
  return fetchJson(`${API_BASE}/api/tasks/${taskId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(userId) },
    body: JSON.stringify({ approved })
  });
}

export async function cancelTask(taskId: string, userId: string) {
  return fetchJson(`${API_BASE}/api/tasks/${taskId}/cancel`, {
    method: "POST",
    headers: authHeaders(userId)
  });
}

export async function fetchToolAudits(caseId?: string) {
  const params = new URLSearchParams();
  if (caseId) params.set("case_id", caseId);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const body = await fetchJson<{ audits: ToolAudit[] }>(`${API_BASE}/api/tool-audits${suffix}`, {
    headers: authHeaders("agent-demo", "agent")
  });
  return body.audits ?? [];
}
