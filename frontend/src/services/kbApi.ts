import type { Citation } from "../types/api";
import { API_BASE, authHeaders, fetchJson } from "./apiClient";

export type KBIngestPayload = {
  title: string;
  content: string;
  source: string;
  category: string;
  tags: string[];
};

export async function searchKnowledge(query: string, category: string, topK = 8) {
  const params = new URLSearchParams({ query, top_k: String(topK) });
  if (category) params.set("category", category);
  const body = await fetchJson<{ documents: Citation[] }>(
    `${API_BASE}/api/kb/search?${params.toString()}`,
    { headers: authHeaders("agent-demo", "agent") }
  );
  return body.documents ?? [];
}

export async function ingestKnowledge(payload: KBIngestPayload) {
  return fetchJson<{ ingested_chunks: number; documents: Citation[] }>(`${API_BASE}/api/kb/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders("admin-demo", "admin") },
    body: JSON.stringify(payload)
  });
}
