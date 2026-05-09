import type { EvalRun } from "../types/api";
import { API_BASE, fetchJson } from "./apiClient";

export async function runEval(size: number) {
  return fetchJson<EvalRun>(`${API_BASE}/api/evals/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ size })
  });
}
