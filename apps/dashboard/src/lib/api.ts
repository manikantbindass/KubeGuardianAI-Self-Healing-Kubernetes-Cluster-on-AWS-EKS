export type Health = { status: "ok"; service: "kubesentinel-api"; version: string };
export type Readiness = { status: "ready" | "unavailable"; dependencies: Record<string, "ok" | "unavailable"> };
export type Version = { version: string; api_version: string; environment: string };
export type Job = { id: string; name: string; status: "queued" | "completed"; message: string | null; created_at: string };

export class ApiError extends Error {
  constructor(public status: number, public correlationId?: string, public code?: string) { super(`API request failed (${status})`); }
}
function record(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null; }
export function isJob(value: unknown): value is Job {
  return record(value) && typeof value.id === "string" && typeof value.name === "string"
    && ["queued", "completed"].includes(String(value.status)) && typeof value.created_at === "string"
    && (value.message === null || typeof value.message === "string");
}
async function request<T>(path: string, valid: (value: unknown) => value is T, init?: RequestInit, allow503 = false): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, { ...init, cache: "no-store", signal: AbortSignal.timeout(8000) });
  const body: unknown = await response.json();
  if (!response.ok && !(allow503 && response.status === 503)) {
    const code = record(body) && record(body.error) && typeof body.error.code === "string" ? body.error.code : undefined;
    throw new ApiError(response.status, response.headers.get("X-Correlation-ID") ?? undefined, code);
  }
  if (!valid(body)) throw new Error("Backend response did not match the API contract.");
  return body;
}
export const api = {
  health: () => request("health", (v): v is Health => record(v) && v.status === "ok" && v.service === "kubesentinel-api" && typeof v.version === "string"),
  ready: () => request("ready", (v): v is Readiness => record(v) && ["ready", "unavailable"].includes(String(v.status)) && record(v.dependencies) && Object.values(v.dependencies).every(s => s === "ok" || s === "unavailable"), undefined, true),
  version: () => request("version", (v): v is Version => record(v) && typeof v.version === "string" && typeof v.api_version === "string" && typeof v.environment === "string"),
  jobs: () => request("jobs", (v): v is Job[] => Array.isArray(v) && v.every(isJob)),
  createJob: (name: string) => request("jobs", isJob, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }),
};
