type ViteEnv = {
  VITE_API_BASE_URL?: string;
  VITE_API_FALLBACK_BASE_URL?: string;
};

const env = ((import.meta as ImportMeta & { env?: ViteEnv }).env ?? {}) as ViteEnv;
const configuredApiBase = env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";
const fallbackApiBase = (env.VITE_API_FALLBACK_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

export const API_BASE = configuredApiBase;

export function apiUrl(path: string) {
  return `${API_BASE}${path}`;
}

export async function fetchApi(url: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(url, init);
  if (response.status !== 404 || configuredApiBase || !url.startsWith("/")) {
    return response;
  }
  try {
    return await fetch(`${fallbackApiBase}${url}`, init);
  } catch {
    return response;
  }
}

export function authHeaders(userId: string, roles = "customer"): Record<string, string> {
  return {
    "X-SmartCS-User": userId,
    "X-SmartCS-Tenant": "demo-tenant",
    "X-SmartCS-Roles": roles
  };
}

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetchApi(url, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}
