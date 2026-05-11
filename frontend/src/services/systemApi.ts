import type { GraphMetadata, HarnessManifest, Health, ToolSpec } from "../types/api";
import { API_BASE, authHeaders, fetchJson } from "./apiClient";

export async function fetchHealth() {
  return fetchJson<Health>(`${API_BASE}/health`);
}

export async function fetchSystemBundle() {
  const headers = authHeaders("admin-demo", "admin");
  const [toolsBody, graph, harness] = await Promise.all([
    fetchJson<{ tools: ToolSpec[] }>(`${API_BASE}/api/tools`, { headers }),
    fetchJson<GraphMetadata>(`${API_BASE}/api/graph`, { headers }),
    fetchJson<HarnessManifest>(`${API_BASE}/api/harness/manifest`, { headers })
  ]);
  return { tools: toolsBody.tools ?? [], graph, harness };
}
