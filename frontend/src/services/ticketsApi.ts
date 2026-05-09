import type { Ticket } from "../types/api";
import { API_BASE, authHeaders, fetchJson } from "./apiClient";

export async function fetchTickets() {
  const body = await fetchJson<{ tickets: Ticket[] }>(`${API_BASE}/api/tickets`);
  return body.tickets ?? [];
}

export async function updateTicket(ticketId: string, payload: Partial<Ticket>) {
  return fetchJson<Ticket>(`${API_BASE}/api/tickets/${ticketId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function handoffCase(caseId: string, userId: string, reason: string) {
  return fetchJson(`${API_BASE}/api/cases/${caseId}/handoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(userId, "agent") },
    body: JSON.stringify({ reason })
  });
}
