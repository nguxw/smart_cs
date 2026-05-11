import type { EvalRun } from "../types/api";
import { API_BASE, authHeaders, fetchJson } from "./apiClient";

export async function runEval(size: number) {
  return fetchJson<EvalRun>(`${API_BASE}/api/evals/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders("admin-demo", "admin") },
    body: JSON.stringify({ size })
  });
}
