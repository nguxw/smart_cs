import type { GraphMetadata, HarnessManifest, Health, ToolSpec } from "../types/api";
import { API_BASE, fetchJson } from "./apiClient";

export async function fetchHealth() {
  return fetchJson<Health>(`${API_BASE}/health`);
}

export async function fetchSystemBundle() {
  const [toolsBody, graph, harness] = await Promise.all([
    fetchJson<{ tools: ToolSpec[] }>(`${API_BASE}/api/tools`),
    fetchJson<GraphMetadata>(`${API_BASE}/api/graph`),
    fetchJson<HarnessManifest>(`${API_BASE}/api/harness/manifest`)
  ]);
  return { tools: toolsBody.tools ?? [], graph, harness };
}
