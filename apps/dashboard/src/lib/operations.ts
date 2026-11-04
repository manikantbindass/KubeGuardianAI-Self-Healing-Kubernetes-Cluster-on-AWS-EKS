export type Mode = "real" | "demo";
export type Section =
  | "overview"
  | "explorer"
  | "workloads"
  | "metrics"
  | "anomalies"
  | "incidents"
  | "actions"
  | "policies"
  | "insights"
  | "audit"
  | "infrastructure"
  | "settings";
export type Session = {
  subject: string;
  name: string;
  roles: string[];
  authentication: string;
  demo_enabled: boolean;
  namespaces: string[];
  data_default: "real";
};
export type Explanation = {
  feature: string;
  value: number;
  reference: number;
  detail: string;
};
export type IncidentIntelligence = {
  engine_version: string;
  mode: Mode;
  assistant: string;
  remote_requests: number;
  explanations: {
    incident_id: string;
    namespace: string;
    resource: string;
    related_ids: string[];
    duplicate_ids: string[];
    historical_similar_ids: string[];
    summary: string;
    evidence_ids: string[];
    hypotheses: {
      id: string;
      label: string;
      rank_score: number;
      evidence: string[];
      uncertainty: string;
    }[];
    runbooks: { id: string; title: string; path: string; steps: string[] }[];
  }[];
  limitations: string[];
};
export type OpsIncident = {
  id: string;
  source: string;
  namespace: string;
  resource: string;
  reason: string;
  summary: string;
  severity: string;
  status: string;
  first_seen: string;
  last_seen: string;
  occurrences: number;
  confidence: number | null;
  confidence_label: string;
  review: { actor: string; note: string; at: string } | null;
};
export type Audit = {
  id: number;
  at: string;
  actor: string;
  verb: string;
  target: string;
  outcome: string;
  correlation_id: string;
  detail: Record<string, unknown>;
};
export type Command = {
  id: string;
  kind: string;
  target: string;
  namespace: string;
  state: string;
  created_at: string;
  expires_at: string;
  actor: string;
  mode: Mode;
  result: string | null;
};
export type ResourceData = {
  status?: {
    phase?: string;
    reason?: string;
    hold?: boolean;
    successes?: number;
    mutationCount?: number;
    approvalActor?: string;
    completedAt?: string;
    before?: { errors: number; requests: number; p95Milliseconds: number };
    after?: { errors: number; requests: number; p95Milliseconds: number };
    audit?: { at: string; actor: string; state: string; reason: string }[];
  };
  spec?: {
    incident?: {
      id: string;
      type: string;
      severity: string;
      source: string;
      observedAt: string;
    };
    target?: {
      name: string;
      uid: string;
      generation: number;
      replicas: number;
    };
    kind?: string;
    expiresAt?: string;
    policyName?: string;
    rollbackEnabled?: boolean;
    budgetCost?: number;
    scaleTo?: number;
    dryRun?: boolean;
    approvalRequired?: boolean;
    cooldownSeconds?: number;
    maxActionsPerWindow?: number;
    maximumReplicas?: number;
    minimumHealthyReplicas?: number;
    incidentTypes?: string[];
    allowedActions?: string[];
    namespaceAllowlist?: string[];
    verification?: {
      timeoutSeconds: number;
      maxP95Milliseconds: number;
      maxErrorBasisPoints: number;
    };
    maintenanceWindows?: {
      weekdays: number[];
      startHour: number;
      endHour: number;
    }[];
  };
  phase?: string;
  healthy?: boolean;
  ready?: number;
  desired?: number;
  restarts?: number;
  node?: string;
  cpu_request?: string;
  memory_request?: string;
  cpu_capacity?: string;
  memory_capacity?: string;
  reason?: string;
  message?: string;
  type?: string;
  timestamp?: string;
  labels?: Record<string, string>;
  containers?: string[];
  conditions?: { type: string; status: string; reason?: string }[];
  owner?: string;
  images?: string[];
  age?: string;
};
export type Resource = {
  id: string;
  kind:
    | "Node"
    | "Deployment"
    | "Pod"
    | "Event"
    | "RemediationAction"
    | "RemediationPolicy";
  namespace: string;
  name: string;
  uid: string;
  resource_version: string;
  collected_at: string;
  data: ResourceData;
};
export type View = {
  mode: Mode;
  generated_at: string;
  namespaces: string[];
  resources: Resource[];
  incidents: OpsIncident[];
  anomaly_evidence: {
    incident_id: string;
    at: string;
    resource: string;
    detector: string;
    model_version: string;
    score: number;
    threshold: number;
    provenance: string;
    explanations: Explanation[];
    score_kind: string;
  }[];
  commands: Command[];
  audit: Audit[];
  summary: {
    nodes: number;
    pods: number;
    workloads: number;
    healthy_workloads: number;
    unhealthy_workloads: number;
    active_incidents: number;
    recoveries: number;
    awaiting_approval: number;
  };
  bridge: {
    last_collected_at: string | null;
    stale: boolean;
    limited: boolean;
    resource_limit: number;
    source: string;
  };
};
export type Series = { source: string; points: [number, number][] };
export type Preferences = {
  refresh_seconds: number;
  compact_tables: boolean;
  timezone: "UTC" | "local";
};
export type ModelHealth = {
  status: string;
  metadata: {
    model_state?: string;
    model_version?: string;
    metadata?: {
      provenance?: string;
      score_kind?: string;
      packages?: Record<string, string>;
    };
  } | null;
  drift: {
    windows_scored?: number;
    extreme_shift_windows?: number;
    shift_rate?: number;
    persistence?: string;
  } | null;
  evaluation: string;
};

export class OperationsError extends Error {
  constructor(
    public status: number,
    message: string,
    public correlationId?: string,
  ) {
    super(message);
  }
}
export async function opsRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api/backend/ops/${path}`, {
    ...init,
    cache: "no-store",
    signal: AbortSignal.timeout(12000),
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = await response.json();
  if (!response.ok)
    throw new OperationsError(
      response.status,
      body.error?.message ?? body.detail ?? "Operations API unavailable",
      response.headers.get("X-Correlation-ID") ?? undefined,
    );
  return body as T;
}
export const operations = {
  session: () => opsRequest<Session>("session"),
  intelligence: (mode: Mode, namespace: string) =>
    opsRequest<IncidentIntelligence>(
      `intelligence?mode=${mode}&namespace=${encodeURIComponent(namespace)}`,
    ),
  view: (mode: Mode, namespace: string) =>
    opsRequest<View>(
      `view?mode=${mode}&namespace=${encodeURIComponent(namespace)}`,
    ),
  metrics: (name: string, mode: Mode, minutes: number) =>
    opsRequest<Series>(`metrics/${name}?mode=${mode}&minutes=${minutes}`),
  model: () => opsRequest<ModelHealth>("model"),
  logs: (resource: Resource, mode: Mode) =>
    opsRequest<{ source: string; lines: { at: string; text: string }[] }>(
      `resources/${resource.id}/logs?mode=${mode}`,
    ),
  preferences: () => opsRequest<Preferences>("preferences"),
  savePreferences: (body: Preferences) =>
    opsRequest<Preferences>("preferences", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  decide: (
    resource: Resource,
    decision: "approve" | "reject",
    reason: string,
    mode: Mode,
    key: string,
  ) =>
    opsRequest<Command>(`actions/${resource.id}/decision?mode=${mode}`, {
      method: "POST",
      body: JSON.stringify({
        decision,
        reason,
        expected_uid: resource.uid,
        expected_version: resource.resource_version,
        idempotency_key: key,
      }),
    }),
  policy: (
    resource: Resource,
    values: {
      dry_run: boolean;
      cooldown_seconds: number;
      maximum_actions: number;
      maximum_replicas: number;
      reason: string;
    },
    mode: Mode,
    key: string,
  ) =>
    opsRequest<Command>(`policies/${resource.id}?mode=${mode}`, {
      method: "POST",
      body: JSON.stringify({
        ...values,
        expected_uid: resource.uid,
        expected_version: resource.resource_version,
        idempotency_key: key,
      }),
    }),
  review: (incident: string, note: string) =>
    opsRequest<{ status: string }>(`incidents/${incident}/review`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  estimate: (values: {
    nodes: number;
    node_hourly: number;
    cluster_hourly: number;
    other_monthly: number;
  }) =>
    opsRequest<{
      monthly: number;
      kind: string;
      hours: number;
      excluded: string[];
    }>("cost-estimate", { method: "POST", body: JSON.stringify(values) }),
};

export function download(
  name: string,
  body: string,
  type = "application/json",
) {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
export function pretty(value: string | number | null | undefined) {
  return value === null || value === undefined || value === ""
    ? "—"
    : String(value);
}
export function timestamp(value: string | null | undefined) {
  let zone: string | undefined = "UTC";
  try {
    if (
      typeof window !== "undefined" &&
      localStorage.getItem("sentinel-event-timezone") === "local"
    )
      zone = undefined;
  } catch {
    /* restricted storage uses UTC */
  }
  return value
    ? new Date(value).toLocaleString(undefined, {
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZone: zone,
      })
    : "Not collected";
}
