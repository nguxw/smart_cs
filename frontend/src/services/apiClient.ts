export const API_BASE = "";

export function authHeaders(userId: string, roles = "customer"): Record<string, string> {
  return {
    "X-SmartCS-User": userId,
    "X-SmartCS-Tenant": "demo-tenant",
    "X-SmartCS-Roles": roles
  };
}

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}
