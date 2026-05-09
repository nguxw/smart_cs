import type { Citation } from "../types/api";
import { API_BASE, fetchJson } from "./apiClient";

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
    `${API_BASE}/api/kb/search?${params.toString()}`
  );
  return body.documents ?? [];
}

export async function ingestKnowledge(payload: KBIngestPayload) {
  return fetchJson<{ ingested_chunks: number; documents: Citation[] }>(`${API_BASE}/api/kb/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}
