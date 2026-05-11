import type { Ticket, TicketThread } from "../types/api";
import { API_BASE, authHeaders, fetchJson } from "./apiClient";

export async function fetchTickets() {
  const body = await fetchJson<{ tickets: Ticket[] }>(`${API_BASE}/api/tickets`, {
    headers: authHeaders("agent-demo", "agent")
  });
  return body.tickets ?? [];
}

export async function updateTicket(ticketId: string, payload: Partial<Ticket>) {
  return fetchJson<Ticket>(`${API_BASE}/api/tickets/${ticketId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders("agent-demo", "agent") },
    body: JSON.stringify(payload)
  });
}

export async function fetchTicketThread(ticketId: string) {
  return fetchJson<TicketThread>(`${API_BASE}/api/tickets/${ticketId}/thread`, {
    headers: authHeaders("agent-demo", "agent")
  });
}

export async function handoffCase(caseId: string, userId: string, reason: string) {
  return fetchJson(`${API_BASE}/api/cases/${caseId}/handoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(userId, "agent") },
    body: JSON.stringify({ reason })
  });
}
