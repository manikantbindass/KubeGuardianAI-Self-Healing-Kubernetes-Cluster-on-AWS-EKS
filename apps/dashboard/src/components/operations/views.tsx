"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Boxes,
  Check,
  ChevronRight,
  CircleHelp,
  Cpu,
  Database,
  FileCheck2,
  FileClock,
  GitBranch,
  Layers3,
  Network,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Workflow,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  download,
  operations,
  timestamp,
  pretty,
  type Mode,
  type OpsIncident,
  type Preferences,
  type Resource,
  type Section,
  type Session,
  type View,
} from "@/lib/operations";
import { Badge, DataTable, Dialog, Empty } from "./primitives";
import { SeverityChart, TimeChart } from "./charts";
import { ClusterCanvas } from "./cluster-canvas";

function useMetric(name: string, mode: Mode, minutes = 60) {
  return useQuery({
    queryKey: ["ops", "metric", name, mode, minutes],
    queryFn: () => operations.metrics(name, mode, minutes),
    refetchInterval: 15000,
    retry: false,
  });
}
function Metric({
  label,
  value,
  sub,
  icon: Icon,
  tone = "cyan",
}: {
  label: string;
  value: string | number;
  sub: string;
  icon: React.ComponentType<{ size?: number; "aria-hidden"?: boolean }>;
  tone?: string;
}) {
  return (
    <section className={`glass metric-card ${tone}`}>
      <div>
        <span>{label}</span>
        <Icon size={17} aria-hidden />
      </div>
      <strong>{value}</strong>
      <p>{sub}</p>
    </section>
  );
}
function PanelTitle({
  title,
  detail,
  action,
  onClick,
}: {
  title: string;
  detail?: string;
  action?: string;
  onClick?: () => void;
}) {
  return (
    <div className="panel-heading">
      <div>
        <h2>{title}</h2>
        {detail && <p>{detail}</p>}
      </div>
      {action && (
        <button className="text-action" onClick={onClick}>
          {action}
          <ArrowUpRight size={14} />
        </button>
      )}
    </div>
  );
}
function Timeline({ resources }: { resources: Resource[] }) {
  return resources.length ? (
    <ol className="timeline">
      {resources.slice(0, 5).map((r) => (
        <li key={r.id}>
          <span className="timeline-icon">
            <Workflow size={14} />
          </span>
          <div>
            <div className="timeline-title">
              <strong>
                {r.data.spec?.kind ?? "Recovery"} ·{" "}
                {r.data.spec?.target?.name ?? r.name}
              </strong>
              <Badge value={r.data.status?.phase} />
            </div>
            <p>
              {r.data.status?.reason ?? "Waiting for operator reconciliation"}
            </p>
            <small>
              {timestamp(r.data.status?.completedAt ?? r.collected_at)}
            </small>
          </div>
        </li>
      ))}
    </ol>
  ) : (
    <Empty
      title="No recovery activity"
      detail="Operator actions appear here after the scoped bridge collects durable action records."
    />
  );
}

export function Overview({
  view,
  mode,
  go,
  open,
}: {
  view: View;
  mode: Mode;
  go: (s: Section) => void;
  open: (r: Resource) => void;
}) {
  const cpu = useMetric("cpu", mode),
    memory = useMetric("memory", mode);
  const model = useQuery({
    queryKey: ["ops", "model"],
    queryFn: operations.model,
    retry: false,
  });
  const actions = view.resources.filter((r) => r.kind === "RemediationAction");
  const known = view.summary.workloads > 0;
  const health = view.bridge.limited
    ? "Partial"
    : !known || !view.summary.nodes
      ? "Unknown"
      : view.bridge.stale && mode === "real"
        ? "Stale"
        : view.summary.unhealthy_workloads ||
            view.resources.some((r) => r.kind === "Node" && !r.data.healthy)
          ? "Degraded"
          : "Healthy";
  return (
    <>
      <ClusterCanvas view={view} mode={mode} go={go} open={open} />
      <div className="section-label">
        <span>OPERATIONS AT A GLANCE</span>
        <span>Evidence before action</span>
      </div>
      <div className="metric-grid">
        <Metric
          label="Cluster health"
          value={health}
          sub={
            known
              ? `${view.summary.nodes} nodes · ${view.summary.pods} pods observed`
              : "Waiting for cluster collection"
          }
          icon={Network}
        />
        <Metric
          label="Active incidents"
          value={view.summary.active_incidents}
          sub="Persisted, unresolved signals"
          icon={TriangleAlert}
          tone="rose"
        />
        <Metric
          label="Healthy workloads"
          value={
            known
              ? `${view.summary.healthy_workloads} / ${view.summary.workloads}`
              : "—"
          }
          sub={
            known
              ? `${view.summary.unhealthy_workloads} need attention`
              : "Readiness not yet observed"
          }
          icon={Boxes}
          tone="green"
        />
        <Metric
          label="Anomaly signals"
          value={view.anomaly_evidence.length}
          sub="Evidence records · uncalibrated"
          icon={Sparkles}
          tone="violet"
        />
        <Metric
          label="Verified recoveries"
          value={view.summary.recoveries}
          sub="Operator verification passed"
          icon={ShieldCheck}
          tone="blue"
        />
        <Metric
          label="Awaiting approval"
          value={view.summary.awaiting_approval}
          sub="No action without required consent"
          icon={FileCheck2}
          tone="amber"
        />
      </div>
      <div className="section-label">
        <span>RESOURCE PULSE</span>
        <span>Observed data, scoped to your workspace</span>
      </div>
      <div className="overview-charts">
        <TimeChart
          title="CPU utilization"
          unit="cores"
          series={cpu.data}
          error={cpu.isError}
          loading={cpu.isPending}
        />
        <TimeChart
          title="Memory working set"
          unit="GB"
          color="#6a97fa"
          series={memory.data}
          error={memory.isError}
          loading={memory.isPending}
        />
        <SeverityChart incidents={view.incidents} />
      </div>
      <div className="overview-secondary">
        <section className="glass panel">
          <PanelTitle
            title="Recent incidents"
            detail="Signals worth your attention"
            action="View all incidents"
            onClick={() => go("incidents")}
          />
          {view.incidents.length ? (
            <div className="incident-preview">
              {view.incidents.slice(0, 5).map((i) => (
                <button key={i.id} onClick={() => go("incidents")}>
                  <span className={`incident-glyph ${i.severity}`}>
                    <TriangleAlert size={17} />
                  </span>
                  <span>
                    <strong>{i.reason}</strong>
                    <small>
                      {i.namespace} / {i.resource}
                    </small>
                  </span>
                  <span className="preview-status">
                    <Badge value={i.severity} />
                    <small>{timestamp(i.last_seen)}</small>
                  </span>
                  <ChevronRight size={15} />
                </button>
              ))}
            </div>
          ) : (
            <Empty
              title="No incidents recorded"
              detail="This is an empty incident store, not a guarantee that every workload is healthy."
            />
          )}
        </section>
        <section className="glass panel">
          <PanelTitle
            title="Recovery activity"
            detail="Intent, verification, and rollback"
            action="Open action center"
            onClick={() => go("actions")}
          />
          <Timeline resources={actions} />
        </section>
      </div>
      <section className="glass panel service-panel">
        <PanelTitle
          title="Connected services"
          detail="Source availability is separate from cluster health"
        />
        <div className="service-grid">
          {[
            {
              title: "Operations API",
              detail: "Persistent read model",
              value: "Connected",
              icon: Database,
            },
            {
              title: "Kubernetes bridge",
              detail: view.bridge.last_collected_at
                ? timestamp(view.bridge.last_collected_at)
                : "No collection received",
              value:
                mode === "demo"
                  ? "Synthetic"
                  : view.bridge.stale
                    ? "Not ready"
                    : "Connected",
              icon: Network,
            },
            {
              title: "Prometheus",
              detail: cpu.isError
                ? "Metrics request unavailable"
                : `${cpu.data?.points.length ?? 0} CPU samples`,
              value:
                mode === "demo"
                  ? "Synthetic"
                  : cpu.isError
                    ? "Offline"
                    : cpu.data?.points.length
                      ? "Connected"
                      : "Awaiting samples",
              icon: Activity,
            },
            {
              title: "Anomaly detector",
              detail:
                model.data?.status === "not_configured"
                  ? "Configure detector endpoint"
                  : "Model and drift interface",
              value:
                model.data?.status === "connected"
                  ? "Connected"
                  : "Not configured",
              icon: Sparkles,
            },
          ].map((s) => (
            <div className="service-tile" key={s.title}>
              <span className="service-icon">
                <s.icon size={19} />
              </span>
              <div>
                <strong>{s.title}</strong>
                <small>{s.detail}</small>
              </div>
              <Badge value={s.value} />
            </div>
          ))}
        </div>
      </section>
      <section className="guardrail-strip">
        <ShieldCheck size={20} />
        <div>
          <strong>Recovery is a controlled operation.</strong>
          <span>
            Dry-run defaults, scoped workloads, signed approvals, and
            verification remain enforced by the operator.
          </span>
        </div>
        <button
          className="text-action"
          onClick={() => {
            const resource = view.resources.find(
              (r) => r.kind === "RemediationPolicy",
            );
            if (resource) open(resource);
            else go("policies");
          }}
        >
          Inspect policies <ArrowRight size={15} />
        </button>
      </section>
    </>
  );
}

function resourceStatus(r: Resource) {
  return r.kind === "Deployment"
    ? r.data.healthy
      ? "Healthy"
      : "Unhealthy"
    : r.kind === "Node"
      ? r.data.healthy
        ? "Ready"
        : "Not ready"
      : (r.data.phase ?? r.data.status?.phase ?? "Observed");
}
export function ResourceExplorer({
  view,
  open,
  dense,
}: {
  view: View;
  open: (r: Resource) => void;
  dense?: boolean;
}) {
  const [kind, setKind] = useState("Deployment");
  return (
    <section className="glass panel">
      <PanelTitle
        title="Cluster inventory"
        detail="Current redacted snapshots from the authorized namespaces"
      />
      <div className="tabs" role="group" aria-label="Resource kind">
        {["Deployment", "Pod", "Node", "Event"].map((k) => (
          <button aria-pressed={kind === k} onClick={() => setKind(k)} key={k}>
            {k === "Event" ? "Events" : `${k}s`}
            <span>{view.resources.filter((r) => r.kind === k).length}</span>
          </button>
        ))}
      </div>
      <DataTable
        key={kind}
        rows={view.resources.filter((r) => r.kind === kind)}
        keyFor={(r) => r.id}
        dense={dense}
        columns={[
          {
            key: "name",
            title: "Resource",
            text: (r) => r.name,
            cell: (r) => (
              <button className="resource-name" onClick={() => open(r)}>
                <span className="resource-icon">
                  {r.kind === "Node" ? <Cpu size={16} /> : <Boxes size={16} />}
                </span>
                <span>
                  <strong>{r.name}</strong>
                  <small>{r.data.owner ?? r.kind}</small>
                </span>
              </button>
            ),
          },
          {
            key: "namespace",
            title: "Namespace",
            text: (r) => r.namespace || "Cluster-scoped",
            cell: (r) => (
              <span className="namespace-tag">{r.namespace || "Cluster"}</span>
            ),
          },
          {
            key: "status",
            title: "Status",
            text: resourceStatus,
            cell: (r) => (
              <Badge
                value={r.kind === "Event" ? r.data.type : resourceStatus(r)}
              />
            ),
          },
          {
            key: "readiness",
            title: kind === "Event" ? "Reason" : "Readiness",
            text: (r) =>
              kind === "Event"
                ? pretty(r.data.reason)
                : r.data.ready !== undefined
                  ? `${r.data.ready} / ${r.data.desired ?? r.data.containers?.length ?? "?"}`
                  : r.data.healthy
                    ? "Ready"
                    : "Not observed",
          },
          {
            key: "resource",
            title:
              kind === "Node"
                ? "Capacity"
                : kind === "Event"
                  ? "Observed"
                  : "Resource requests",
            text: (r) =>
              kind === "Node"
                ? `${pretty(r.data.cpu_capacity)} CPU · ${pretty(r.data.memory_capacity)}`
                : kind === "Event"
                  ? timestamp(r.data.timestamp)
                  : `${pretty(r.data.cpu_request)} CPU · ${pretty(r.data.memory_request)}`,
          },
          {
            key: "restarts",
            title: "Restarts",
            text: (r) => pretty(r.data.restarts),
          },
        ]}
      />
      <p className="panel-footnote">
        Requests and capacity are configuration, not measured utilization. Open
        Live Metrics for observed time series.
      </p>
    </section>
  );
}

export function MetricsView({ mode }: { mode: Mode }) {
  const [minutes, setMinutes] = useState(60);
  const cpu = useMetric("cpu", mode, minutes),
    memory = useMetric("memory", mode, minutes),
    latency = useMetric("latency", mode, minutes),
    requests = useMetric("requests", mode, minutes);
  return (
    <>
      <div className="view-toolbar">
        <span className="muted">
          Bounded Prometheus range queries · no arbitrary PromQL
        </span>
        <label>
          Time range
          <select
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
          >
            <option value={15}>Last 15 minutes</option>
            <option value={60}>Last hour</option>
            <option value={360}>Last 6 hours</option>
          </select>
        </label>
      </div>
      <div className="two-column">
        {[
          { title: "CPU utilization", unit: "cores", data: cpu },
          { title: "Memory working set", unit: "GB", data: memory },
          { title: "Application p95 latency", unit: "ms", data: latency },
          { title: "Application requests", unit: "req/s", data: requests },
        ].map((item, i) => (
          <TimeChart
            key={item.title}
            title={item.title}
            unit={item.unit}
            color={i % 2 ? "#6a97fa" : "#48c8df"}
            series={item.data.data}
            error={item.data.isError}
            loading={item.data.isPending}
          />
        ))}
      </div>
    </>
  );
}

export function AnomalyView({ view }: { view: View }) {
  const model = useQuery({
    queryKey: ["ops", "model"],
    queryFn: operations.model,
    retry: false,
  });
  const [selected, setSelected] = useState("");
  const evidence =
    view.anomaly_evidence.find((a) => a.incident_id === selected) ??
    view.anomaly_evidence[0];
  const series = {
    source: view.mode === "demo" ? "synthetic" : "incident evidence",
    points: [...view.anomaly_evidence]
      .sort((a, b) => a.at.localeCompare(b.at))
      .map(
        (a) => [new Date(a.at).getTime() / 1000, a.score] as [number, number],
      ),
  };
  return (
    <>
      <div className="three-column">
        <Metric
          label="Model interface"
          value={
            model.data?.status === "connected"
              ? (model.data.metadata?.model_state ?? "Connected")
              : "Not connected"
          }
          sub="Live metadata, no inferred health"
          icon={Sparkles}
        />
        <Metric
          label="Extreme-shift windows"
          value={model.data?.drift?.extreme_shift_windows ?? "—"}
          sub="Process-lifetime advisory drift count"
          icon={Activity}
          tone="violet"
        />
        <Metric
          label="Live false-positive rate"
          value="Not measured"
          sub="Requires independent incident labels"
          icon={CircleHelp}
          tone="amber"
        />
      </div>
      <div className="two-column">
        <TimeChart
          title="Recorded anomaly scores"
          unit="score"
          series={series}
        />
        <section className="glass panel">
          <PanelTitle
            title="Feature evidence"
            detail="Robust deviations, not causal contributions or SHAP values"
          />
          {evidence ? (
            <>
              <label className="field-label">
                Evidence record
                <select
                  value={evidence.incident_id}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  {view.anomaly_evidence.map((a) => (
                    <option key={a.incident_id} value={a.incident_id}>
                      {a.resource} · {timestamp(a.at)}
                    </option>
                  ))}
                </select>
              </label>
              <div className="feature-bars">
                {evidence.explanations.map((e) => {
                  const difference = Math.abs(e.value - e.reference);
                  const maximum = Math.max(
                    ...evidence.explanations.map((v) =>
                      Math.abs(v.value - v.reference),
                    ),
                    1,
                  );
                  return (
                    <div key={e.feature}>
                      <div>
                        <span>{e.feature.replaceAll("_", " ")}</span>
                        <strong>
                          {difference.toLocaleString(undefined, {
                            maximumFractionDigits: 3,
                          })}
                        </strong>
                      </div>
                      <div className="bar-track">
                        <i
                          style={{ width: `${(difference / maximum) * 100}%` }}
                        />
                      </div>
                      <p>{e.detail}</p>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <Empty
              title="No feature evidence"
              detail="Anomaly incident evidence will appear when a detector records explainable scores."
            />
          )}
        </section>
      </div>
      <section className="glass panel">
        <PanelTitle
          title="Model lineage & calibration"
          detail="What the evidence can—and cannot—tell you"
        />
        {evidence ? (
          <div className="detail-grid">
            <div>
              <span>Detector</span>
              <strong>{evidence.detector}</strong>
            </div>
            <div>
              <span>Training/model version</span>
              <code>{evidence.model_version}</code>
            </div>
            <div>
              <span>Score / threshold</span>
              <strong>
                {evidence.score.toFixed(4)} / {evidence.threshold.toFixed(4)}
              </strong>
            </div>
            <div>
              <span>Provenance</span>
              <Badge value={evidence.provenance} />
            </div>
          </div>
        ) : (
          <p className="muted">
            No model-backed incident has been persisted in this data mode.
          </p>
        )}
        <div className="notice">
          <CircleHelp size={19} />
          <p>
            Scores are uncalibrated, not confidence percentages. Synthetic
            benchmark accuracy does not establish performance on real workloads.
            Model drift indicators are advisory; no automatic model promotion
            occurs.
          </p>
        </div>
      </section>
    </>
  );
}

function IncidentDialog({
  incident,
  view,
  session,
  close,
  open,
}: {
  incident: OpsIncident;
  view: View;
  session: Session;
  close: () => void;
  open: (r: Resource) => void;
}) {
  const client = useQueryClient();
  const [note, setNote] = useState("");
  const review = useMutation({
    mutationFn: () => operations.review(incident.id, note),
    onSuccess: () => {
      setNote("");
      void client.invalidateQueries({ queryKey: ["ops", "view"] });
    },
  });
  const related = view.resources.filter(
    (r) =>
      r.kind === "RemediationAction" &&
      (r.data.spec?.target?.name === incident.resource ||
        incident.resource === r.data.spec?.target?.name),
  );
  const explanation = /oom|memory/i.test(incident.reason)
    ? "Memory pressure or a recent workload change may explain the termination. Inspect the actual container limits and rollout history."
    : /backoff|crash|restart/i.test(incident.reason)
      ? "Container startup or configuration failure is a candidate. A restart alone may not correct the underlying configuration."
      : "Review the observed event and workload conditions before choosing a policy-approved response.";
  return (
    <Dialog title={incident.reason} close={close}>
      <div className="detail-badges">
        <Badge value={incident.severity} />
        <Badge value={incident.status} />
        <span className="namespace-tag">{incident.source}</span>
      </div>
      <p className="detail-summary">{incident.summary}</p>
      <div className="detail-grid">
        <div>
          <span>Affected resource</span>
          <strong>
            {incident.namespace} / {incident.resource}
          </strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{incident.confidence_label ?? "Not calibrated"}</strong>
        </div>
        <div>
          <span>First seen</span>
          <strong>{timestamp(incident.first_seen)}</strong>
        </div>
        <div>
          <span>Last observed</span>
          <strong>{timestamp(incident.last_seen)}</strong>
        </div>
      </div>
      <div className="insight-note">
        <Sparkles size={19} />
        <div>
          <h3>Investigation candidate</h3>
          <p>{explanation}</p>
          <small>
            Rule-derived investigation guidance. Not a confirmed root cause.
          </small>
        </div>
      </div>
      <h3>Linked recovery evidence</h3>
      {related.length ? (
        related.map((r) => (
          <button
            key={r.id}
            className="linked-resource"
            onClick={() => {
              close();
              open(r);
            }}
          >
            <Workflow size={17} />
            <span>
              {r.data.spec?.kind} · {r.name}
            </span>
            <Badge value={r.data.status?.phase} />
            <ChevronRight size={15} />
          </button>
        ))
      ) : (
        <p className="muted">
          No exact workload-linked operator action was collected. Do not execute
          a suggestion directly.
        </p>
      )}
      {incident.review && (
        <div className="notice">
          <FileClock size={18} />
          <div>
            <strong>Reviewed by {incident.review.actor}</strong>
            <p>{incident.review.note}</p>
          </div>
        </div>
      )}
      {view.mode === "real" &&
        session.roles.some((r) => ["operator", "admin"].includes(r)) && (
          <form
            className="stack-form"
            onSubmit={(e) => {
              e.preventDefault();
              review.mutate();
            }}
          >
            <label htmlFor="review-note">Add investigation note</label>
            <textarea
              id="review-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              minLength={5}
              maxLength={512}
              required
              placeholder="Record what you investigated. This does not resolve telemetry or approve recovery."
            />
            <Button disabled={review.isPending || note.length < 5}>
              {review.isPending ? "Saving…" : "Save review note"}
            </Button>
            {review.isSuccess && (
              <p role="status" className="success-text">
                Review saved to the persistent incident record.
              </p>
            )}
            {review.isError && (
              <p role="alert" className="error-text">
                {review.error.message}
              </p>
            )}
          </form>
        )}
    </Dialog>
  );
}

export function IncidentCenter({
  view,
  session,
  open,
}: {
  view: View;
  session: Session;
  open: (r: Resource) => void;
}) {
  const [severity, setSeverity] = useState("all");
  const [selected, setSelected] = useState<OpsIncident | null>(null);
  return (
    <>
      <div className="view-toolbar">
        <div className="tabs" aria-label="Severity filter">
          {["all", "critical", "warning", "info"].map((s) => (
            <button
              key={s}
              aria-pressed={severity === s}
              onClick={() => setSeverity(s)}
              className={severity === s ? "selected" : ""}
            >
              {s === "all" ? "All severities" : s}
            </button>
          ))}
        </div>
        <span className="tiny-label">Live changes reconnect automatically</span>
      </div>
      <section className="glass panel">
        <PanelTitle
          title="Incident feed"
          detail="Telemetry records retain their source and evidence"
        />
        <DataTable
          rows={view.incidents.filter(
            (i) => severity === "all" || i.severity === severity,
          )}
          keyFor={(i) => i.id}
          columns={[
            {
              key: "reason",
              title: "Incident",
              text: (i) => i.reason,
              cell: (i) => (
                <button className="table-link" onClick={() => setSelected(i)}>
                  <strong>{i.reason}</strong>
                  <small>{i.summary.slice(0, 82)}</small>
                </button>
              ),
            },
            {
              key: "severity",
              title: "Severity",
              text: (i) => i.severity,
              cell: (i) => <Badge value={i.severity} />,
            },
            {
              key: "workload",
              title: "Affected workload",
              text: (i) => `${i.namespace}/${i.resource}`,
            },
            { key: "source", title: "Detection source", text: (i) => i.source },
            {
              key: "status",
              title: "Status",
              text: (i) => i.status,
              cell: (i) => <Badge value={i.status} />,
            },
            {
              key: "last",
              title: "Last seen",
              text: (i) => timestamp(i.last_seen),
            },
          ]}
        />
      </section>
      {selected && (
        <IncidentDialog
          incident={selected}
          view={view}
          session={session}
          close={() => setSelected(null)}
          open={open}
        />
      )}
    </>
  );
}

function DecisionForm({
  resource,
  mode,
  session,
  done,
}: {
  resource: Resource;
  mode: Mode;
  session: Session;
  done: () => void;
}) {
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [key] = useState(() => crypto.randomUUID());
  const mutation = useMutation({
    mutationFn: (decision: "approve" | "reject") =>
      operations.decide(resource, decision, reason, mode, key),
  });
  const can = session.roles.some((r) => ["approver", "admin"].includes(r));
  if (resource.data.status?.phase !== "AwaitingApproval")
    return (
      <div className="notice">
        <ShieldCheck size={19} />
        <p>
          This action is{" "}
          {resource.data.status?.phase ?? "not awaiting approval"}. Decisions
          are accepted only before execution starts.
        </p>
      </div>
    );
  if (!can)
    return (
      <div className="notice">
        <ShieldCheck size={19} />
        <p>
          Your role can inspect this plan. An approver or administrator must
          authorize or reject it.
        </p>
      </div>
    );
  return (
    <div className="decision-form">
      <h3>Review the exact plan</h3>
      <p>
        Approval binds the workload UID, generation, policy version, expiry and
        declared rollback consent. The operator rechecks every safety
        constraint.
      </p>
      <label htmlFor="decision-reason">Decision reason</label>
      <textarea
        id="decision-reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        minLength={10}
        maxLength={512}
        placeholder="Explain the evidence and why this exact action is appropriate."
      />
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        I reviewed the target, policy, availability and rollback scope.
      </label>
      <div className="button-row">
        <Button
          disabled={
            !confirmed ||
            reason.length < 10 ||
            mutation.isPending ||
            mutation.isSuccess
          }
          onClick={() => mutation.mutate("approve")}
        >
          <ShieldCheck size={15} />
          {mode === "demo" ? "Record demo approval" : "Approve exact plan"}
        </Button>
        <Button
          variant="outline"
          disabled={
            reason.length < 10 || mutation.isPending || mutation.isSuccess
          }
          onClick={() => mutation.mutate("reject")}
        >
          Reject plan
        </Button>
      </div>
      {mutation.isError && (
        <p role="alert" className="error-text">
          {mutation.error.message}
        </p>
      )}
      {mutation.data && (
        <div className="notice" role="status">
          <Check size={18} />
          <div>
            <strong>
              {mutation.data.state === "demo_recorded"
                ? "Synthetic decision recorded"
                : "Decision queued for delivery"}
            </strong>
            <p>
              {mutation.data.result ??
                "This is not execution success. Track bridge delivery and the operator's independently verified outcome."}
            </p>
            <button className="text-action" onClick={done}>
              Track command and action state <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function ActionCenter({
  view,
  session,
  open,
}: {
  view: View;
  session: Session;
  open: (r: Resource) => void;
}) {
  const rows = view.resources.filter((r) => r.kind === "RemediationAction");
  return (
    <>
      <div className="three-column">
        <Metric
          label="Awaiting approval"
          value={view.summary.awaiting_approval}
          sub="Exact plans, not blanket consent"
          icon={FileCheck2}
          tone="amber"
        />
        <Metric
          label="Verified recoveries"
          value={view.summary.recoveries}
          sub="Rollout and service verification passed"
          icon={ShieldCheck}
          tone="green"
        />
        <Metric
          label="Safety holds"
          value={rows.filter((r) => r.data.status?.hold).length}
          sub="Require explicit investigation"
          icon={TriangleAlert}
          tone="rose"
        />
      </div>
      <section className="glass panel">
        <PanelTitle
          title="Self-healing action records"
          detail="Durable operator intent, effects, verification and undo"
        />
        <DataTable
          rows={rows}
          keyFor={(r) => r.id}
          columns={[
            {
              key: "target",
              title: "Workload / action",
              text: (r) => r.data.spec?.target?.name ?? r.name,
              cell: (r) => (
                <button className="table-link" onClick={() => open(r)}>
                  <strong>{r.data.spec?.target?.name ?? r.name}</strong>
                  <small>
                    {r.data.spec?.kind} · {r.data.spec?.incident?.type}
                  </small>
                </button>
              ),
            },
            {
              key: "state",
              title: "State",
              text: (r) => r.data.status?.phase ?? "Pending",
              cell: (r) => <Badge value={r.data.status?.phase} />,
            },
            {
              key: "policy",
              title: "Policy",
              text: (r) => r.data.spec?.policyName ?? "—",
            },
            {
              key: "approval",
              title: "Approval",
              text: (r) =>
                r.data.status?.approvalActor ??
                (r.data.status?.phase === "AwaitingApproval"
                  ? "Required"
                  : "Not recorded"),
            },
            {
              key: "attempts",
              title: "Attempts",
              text: (r) => String(r.data.status?.mutationCount ?? 0),
            },
            {
              key: "observed",
              title: "Observed",
              text: (r) => timestamp(r.collected_at),
            },
          ]}
        />
      </section>
      <section className="glass panel">
        <PanelTitle
          title="Decision delivery"
          detail="Queued commands are not successful recovery actions"
        />
        <DataTable
          rows={view.commands}
          keyFor={(c) => c.id}
          columns={[
            { key: "target", title: "Target", text: (c) => c.target },
            { key: "kind", title: "Request", text: (c) => c.kind },
            {
              key: "state",
              title: "Delivery",
              text: (c) => c.state,
              cell: (c) => <Badge value={c.state} />,
            },
            { key: "actor", title: "Actor", text: (c) => c.actor },
            {
              key: "result",
              title: "Result",
              text: (c) => c.result ?? "Waiting for scoped bridge",
            },
          ]}
        />
      </section>
      <p className="panel-footnote">
        Role: {session.roles.join(", ")}. The UI cannot bypass namespace,
        cooldown, budget, maintenance or minimum-availability constraints.
      </p>
    </>
  );
}

export function ResourceDetail({
  resource,
  view,
  session,
  close,
  refresh,
}: {
  resource: Resource;
  view?: View;
  session: Session;
  close: () => void;
  refresh: () => void;
}) {
  const current = view?.resources.find((r) => r.id === resource.id) ?? resource;
  const status = current.data.status;
  const events =
    view?.resources.filter(
      (r) =>
        r.kind === "Event" &&
        (r.data.owner === current.name ||
          r.data.message?.includes(current.name)),
    ) ?? [];
  return (
    <Dialog title={current.name} close={close}>
      <div className="detail-badges">
        <span className="namespace-tag">{current.kind}</span>
        <span className="namespace-tag">{current.namespace || "Cluster"}</span>
        <Badge
          value={
            current.kind === "RemediationAction"
              ? status?.phase
              : resourceStatus(current)
          }
        />
      </div>
      {current.kind === "RemediationAction" ? (
        <>
          <div className="detail-grid">
            <div>
              <span>Action / target</span>
              <strong>
                {current.data.spec?.kind} · {current.data.spec?.target?.name}
              </strong>
            </div>
            <div>
              <span>Policy</span>
              <strong>{current.data.spec?.policyName}</strong>
            </div>
            <div>
              <span>Plan expiry</span>
              <strong>{timestamp(current.data.spec?.expiresAt)}</strong>
            </div>
            <div>
              <span>Rollback consent / budget</span>
              <strong>
                {current.data.spec?.rollbackEnabled
                  ? "Explicitly included"
                  : "Not enabled"}{" "}
                · {current.data.spec?.budgetCost} units
              </strong>
            </div>
            <div>
              <span>Verification before → after</span>
              <strong>
                {status?.before
                  ? `${status.before.errors}/${status.before.requests} errors · ${status.before.p95Milliseconds} ms`
                  : "Not sampled"}{" "}
                →{" "}
                {status?.after
                  ? `${status.after.errors}/${status.after.requests} errors · ${status.after.p95Milliseconds} ms`
                  : "Not sampled"}
              </strong>
            </div>
            <div>
              <span>Outcome</span>
              <strong>{status?.reason ?? "Waiting for reconciliation"}</strong>
            </div>
          </div>
          {status?.hold && (
            <div className="notice error">
              <TriangleAlert size={19} />
              <p>
                A safety hold blocks further actions. Investigate the exact
                workload and audit; the dashboard cannot silently clear it.
              </p>
            </div>
          )}
          <h3>Execution timeline</h3>
          {status?.audit?.length ? (
            <ol className="timeline">
              {status.audit.map((event, i) => (
                <li key={i}>
                  <span className="timeline-icon">
                    <FileClock size={13} />
                  </span>
                  <div>
                    <div className="timeline-title">
                      <strong>{event.state}</strong>
                      <small>{timestamp(event.at)}</small>
                    </div>
                    <p>{event.reason}</p>
                    <small>Actor · {event.actor}</small>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">No transitions observed.</p>
          )}
          <DecisionForm
            resource={current}
            mode={view?.mode ?? "real"}
            session={session}
            done={refresh}
          />
        </>
      ) : (
        <>
          <div className="detail-grid">
            <div>
              <span>UID</span>
              <code>{current.uid}</code>
            </div>
            <div>
              <span>Resource version</span>
              <code>{current.resource_version}</code>
            </div>
            <div>
              <span>Last collected</span>
              <strong>{timestamp(current.collected_at)}</strong>
            </div>
            <div>
              <span>Images</span>
              <strong>
                {current.data.images?.join(", ") ?? "Not applicable"}
              </strong>
            </div>
          </div>
          <h3>Observed conditions</h3>
          {current.data.conditions?.length ? (
            <ul className="conditions">
              {current.data.conditions.map((c) => (
                <li key={c.type}>
                  <span>{c.type}</span>
                  <Badge value={c.status} />
                  <small>{c.reason}</small>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">
              No condition fields were collected for this record.
            </p>
          )}
          <h3>Related events</h3>
          {events.length ? (
            events.map((event) => (
              <div className="event-record" key={event.id}>
                <Badge value={event.data.type} />
                <strong>{event.data.reason}</strong>
                <p>{event.data.message}</p>
                <small>{timestamp(event.data.timestamp)}</small>
              </div>
            ))
          ) : (
            <p className="muted">
              No exact related events were collected. Raw container logs are
              intentionally not copied into this read model.
            </p>
          )}
          {current.kind === "Pod" && (
            <PodLogs resource={current} mode={view?.mode ?? "real"} />
          )}
          <details className="raw-evidence">
            <summary>Inspect collected record</summary>
            <pre>{JSON.stringify(current.data, null, 2)}</pre>
          </details>
        </>
      )}
      <Button
        variant="outline"
        onClick={() =>
          download(
            `${current.name}-evidence.json`,
            JSON.stringify(current, null, 2),
          )
        }
      >
        <ArrowDownToLine size={15} />
        Export this evidence
      </Button>
    </Dialog>
  );
}

function PodLogs({ resource, mode }: { resource: Resource; mode: Mode }) {
  const [enabled, setEnabled] = useState(false);
  const logs = useQuery({
    queryKey: ["ops", "logs", resource.id, mode],
    queryFn: () => operations.logs(resource, mode),
    enabled,
    retry: false,
  });
  return (
    <section className="raw-evidence">
      <h3>Pod logs · last 15 minutes</h3>
      <p className="muted">
        Up to 100 entries. Requires Loki pod and namespace metadata.
      </p>
      <Button
        variant="outline"
        onClick={() => {
          setEnabled(true);
          if (enabled) void logs.refetch();
        }}
      >
        Load pod logs
      </Button>
      {logs.isFetching && <p role="status">Loading logs…</p>}
      {logs.isError && (
        <p role="alert">Log source unavailable. No synthetic fallback.</p>
      )}
      {logs.data && (
        <>
          <p className="muted">Source: {logs.data.source}</p>
          {logs.data.lines.length ? (
            <pre>
              {logs.data.lines
                .map(
                  (l) =>
                    `${new Date(Number(l.at) / 1e6).toISOString()} ${l.text}`,
                )
                .join("\n")}
            </pre>
          ) : (
            <p>No matching log entries. Check collection and metadata.</p>
          )}
        </>
      )}
    </section>
  );
}

function PolicyEditor({
  resource,
  view,
  close,
}: {
  resource: Resource;
  view: View;
  close: () => void;
}) {
  const spec = resource.data.spec;
  const [dry, setDry] = useState(spec?.dryRun ?? true);
  const [cooldown, setCooldown] = useState(spec?.cooldownSeconds ?? 300);
  const [budget, setBudget] = useState(spec?.maxActionsPerWindow ?? 2);
  const [replicas, setReplicas] = useState(spec?.maximumReplicas ?? 4);
  const [reason, setReason] = useState("");
  const [key] = useState(() => crypto.randomUUID());
  const mutation = useMutation({
    mutationFn: () =>
      operations.policy(
        resource,
        {
          dry_run: dry,
          cooldown_seconds: cooldown,
          maximum_actions: budget,
          maximum_replicas: replicas,
          reason,
        },
        view.mode,
        key,
      ),
  });
  return (
    <Dialog title={`Edit policy · ${resource.name}`} close={close}>
      <div className="notice">
        <ShieldCheck size={19} />
        <p>
          Changing a policy invalidates old plans and approvals. Global operator
          execution, signed risky-action consent and minimum availability remain
          independently enforced.
        </p>
      </div>
      <form
        className="stack-form"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={dry}
            onChange={(e) => setDry(e.target.checked)}
          />
          Dry-run only
        </label>
        <div className="two-column">
          <label>
            Cooldown (seconds)
            <input
              type="number"
              min={0}
              max={86400}
              value={cooldown}
              onChange={(e) => setCooldown(Number(e.target.value))}
            />
          </label>
          <label>
            Maximum actions per window
            <input
              type="number"
              min={1}
              max={20}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
            />
          </label>
          <label>
            Maximum replicas
            <input
              type="number"
              min={spec?.minimumHealthyReplicas ?? 1}
              max={100}
              value={replicas}
              onChange={(e) => setReplicas(Number(e.target.value))}
            />
          </label>
        </div>
        <label>
          Change reason
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            minLength={10}
            maxLength={512}
            required
          />
        </label>
        <Button
          disabled={
            reason.length < 10 || mutation.isPending || mutation.isSuccess
          }
        >
          {mutation.isPending
            ? "Submitting…"
            : view.mode === "demo"
              ? "Record synthetic policy change"
              : "Submit version-checked change"}
        </Button>
        {mutation.isError && (
          <p role="alert" className="error-text">
            {mutation.error.message}
          </p>
        )}
        {mutation.data && (
          <p role="status" className="success-text">
            {mutation.data.state === "demo_recorded"
              ? "Synthetic change recorded. Nothing was sent to Kubernetes."
              : "Change queued. Track delivery in Self-Healing Actions; it is not applied until the bridge confirms it."}
          </p>
        )}
      </form>
    </Dialog>
  );
}

export function PolicyCenter({
  view,
  session,
}: {
  view: View;
  session: Session;
}) {
  const [selected, setSelected] = useState<Resource | null>(null);
  const rows = view.resources.filter((r) => r.kind === "RemediationPolicy");
  return (
    <>
      <div className="notice">
        <ShieldCheck size={19} />
        <p>
          Policies narrow execution authority; they do not grant cluster-wide
          access. Dry-run, maintenance, cooldown, action budgets and signed
          approvals are independent gates.
        </p>
      </div>
      {rows.length ? (
        <div className="policy-grid">
          {rows.map((r) => (
            <section className="glass panel policy-card" key={r.id}>
              <div className="panel-heading">
                <div className="policy-title">
                  <span className="service-icon">
                    <ShieldCheck size={20} />
                  </span>
                  <div>
                    <h2>{r.name}</h2>
                    <p>{r.namespace}</p>
                  </div>
                </div>
                <Badge
                  value={r.data.spec?.dryRun ? "Dry-run" : "Execution eligible"}
                />
              </div>
              <div className="detail-grid">
                <div>
                  <span>Allowed actions</span>
                  <strong>{r.data.spec?.allowedActions?.join(", ")}</strong>
                </div>
                <div>
                  <span>Signed approval</span>
                  <strong>
                    {r.data.spec?.approvalRequired
                      ? "Required"
                      : "Risky actions still require consent"}
                  </strong>
                </div>
                <div>
                  <span>Cooldown</span>
                  <strong>{r.data.spec?.cooldownSeconds}s</strong>
                </div>
                <div>
                  <span>Action budget</span>
                  <strong>{r.data.spec?.maxActionsPerWindow} / window</strong>
                </div>
                <div>
                  <span>Minimum healthy</span>
                  <strong>
                    {r.data.spec?.minimumHealthyReplicas} replicas
                  </strong>
                </div>
                <div>
                  <span>Maximum replicas</span>
                  <strong>{r.data.spec?.maximumReplicas}</strong>
                </div>
              </div>
              <div className="policy-types">
                {r.data.spec?.incidentTypes?.map((type) => (
                  <span key={type}>{type}</span>
                ))}
              </div>
              {session.roles.includes("admin") ? (
                <Button variant="outline" onClick={() => setSelected(r)}>
                  Review and edit policy <ArrowUpRight size={15} />
                </Button>
              ) : (
                <p className="muted">
                  Administrator role required to change policy.
                </p>
              )}
            </section>
          ))}
        </div>
      ) : (
        <section className="glass panel">
          <Empty
            title="No policies collected"
            detail="Install a scoped RemediationPolicy and connect the operations bridge. No automatic default policy is invented."
          />
        </section>
      )}
      {selected && (
        <PolicyEditor
          resource={selected}
          view={view}
          close={() => setSelected(null)}
        />
      )}
    </>
  );
}

export function InsightsView({
  view,
  go,
}: {
  view: View;
  go: (s: Section) => void;
}) {
  const incidents = view.incidents.slice(0, 10);
  const links = incidents.flatMap((a, i) =>
    incidents
      .slice(i + 1)
      .filter((b) => a.resource === b.resource)
      .map((b) => [a.id, b.id]),
  );
  return (
    <>
      <div className="insight-note">
        <Sparkles size={23} />
        <div>
          <h2>Evidence-led insights</h2>
          <p>
            These summaries and links are derived from observed records. No LLM
            provider is connected, and no root cause or confidence score is
            invented.
          </p>
        </div>
      </div>
      <div className="two-column">
        <section className="glass panel">
          <PanelTitle
            title="Incident relationship map"
            detail="Edges mean shared affected resource, not confirmed causation"
          />
          {incidents.length ? (
            <svg
              className="correlation-graph"
              viewBox="0 0 520 300"
              role="img"
              aria-label={`${incidents.length} incident records and ${links.length} shared-resource relationships`}
            >
              {links.map(([a, b], i) => {
                const x = incidents.findIndex((n) => n.id === a),
                  y = incidents.findIndex((n) => n.id === b);
                return (
                  <line
                    key={i}
                    x1={80 + (x % 3) * 175}
                    y1={45 + Math.floor(x / 3) * 70}
                    x2={80 + (y % 3) * 175}
                    y2={45 + Math.floor(y / 3) * 70}
                    stroke="#3b7088"
                  />
                );
              })}
              {incidents.map((i, n) => (
                <g key={i.id}>
                  <circle
                    cx={80 + (n % 3) * 175}
                    cy={45 + Math.floor(n / 3) * 70}
                    r="12"
                    fill="#102b3f"
                    stroke={i.severity === "critical" ? "#fa718b" : "#56c6de"}
                  />
                  <text
                    x={80 + (n % 3) * 175}
                    y={71 + Math.floor(n / 3) * 70}
                    textAnchor="middle"
                    fill="#c0cee0"
                    fontSize="10"
                  >
                    {i.reason.slice(0, 22)}
                  </text>
                </g>
              ))}
            </svg>
          ) : (
            <Empty
              title="No relationships to show"
              detail="Connections appear only when actual incident records share an affected workload."
            />
          )}
          <Button variant="outline" onClick={() => go("incidents")}>
            Inspect incident evidence <ArrowRight size={15} />
          </Button>
        </section>
        <section className="glass panel">
          <PanelTitle
            title="Investigation priorities"
            detail="Deterministic observations, with explicit limits"
          />
          {view.summary.active_incidents ? (
            <div className="insight-item">
              <TriangleAlert size={20} />
              <div>
                <h3>{view.summary.active_incidents} unresolved signals</h3>
                <p>
                  Inspect recent severity and affected workloads before
                  proposing a response.
                </p>
                <button className="text-action" onClick={() => go("incidents")}>
                  Review incident center <ArrowRight size={14} />
                </button>
              </div>
            </div>
          ) : (
            <p className="muted">
              No unresolved incidents are stored in this mode. This alone does
              not establish cluster health.
            </p>
          )}
          <div className="insight-item">
            <ShieldCheck size={20} />
            <div>
              <h3>{view.summary.awaiting_approval} plans awaiting consent</h3>
              <p>
                Review exact scope, before measurements, rollback consent and
                current policy version.
              </p>
              <button className="text-action" onClick={() => go("actions")}>
                Review action plans <ArrowRight size={14} />
              </button>
            </div>
          </div>
          <div className="insight-item">
            <GitBranch size={20} />
            <div>
              <h3>{links.length} shared-workload links</h3>
              <p>
                Temporal overlap and shared resources are clues, not proof of
                causal incident correlation.
              </p>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}

export function AuditView({ view }: { view: View }) {
  const records = view.audit.filter((a) => a.verb !== "snapshot.refresh");
  return (
    <section className="glass panel">
      <PanelTitle
        title="Operations audit trail"
        detail="PostgreSQL-backed actor, request, decision and delivery records"
        action="Export audit JSON"
        onClick={() =>
          download(
            `audit-${view.mode}.json`,
            JSON.stringify(view.audit, null, 2),
          )
        }
      />
      <DataTable
        rows={records}
        keyFor={(a) => String(a.id)}
        columns={[
          { key: "time", title: "Timestamp", text: (a) => timestamp(a.at) },
          { key: "actor", title: "Actor", text: (a) => a.actor },
          { key: "verb", title: "Operation", text: (a) => a.verb },
          { key: "target", title: "Target", text: (a) => a.target },
          {
            key: "outcome",
            title: "Result",
            text: (a) => a.outcome,
            cell: (a) => <Badge value={a.outcome} />,
          },
          {
            key: "correlation",
            title: "Request ID",
            text: (a) => a.correlation_id,
          },
        ]}
      />
      <p className="panel-footnote">
        Collection heartbeat records are included in JSON export. Operator
        transition audit lives on each recovery action. This store is durable,
        not an external immutable compliance archive.
      </p>
    </section>
  );
}

export function InfrastructureView({ view }: { view: View }) {
  const [nodes, setNodes] = useState(view.summary.nodes);
  const [hourly, setHourly] = useState(0);
  const [cluster, setCluster] = useState(0);
  const [other, setOther] = useState(0);
  const estimate = useMutation({
    mutationFn: () =>
      operations.estimate({
        nodes,
        node_hourly: hourly,
        cluster_hourly: cluster,
        other_monthly: other,
      }),
  });
  return (
    <>
      <div className="notice">
        <Layers3 size={20} />
        <p>
          This workspace observes Kubernetes resources. AWS infrastructure
          source is not proof of a deployed EKS cluster, and no AWS billing
          account is connected.
        </p>
      </div>
      <div className="three-column">
        <Metric
          label="Observed nodes"
          value={view.summary.nodes}
          sub="From the selected collection mode"
          icon={Cpu}
        />
        <Metric
          label="Observed deployments"
          value={view.summary.workloads}
          sub="Authorized namespaces only"
          icon={Boxes}
        />
        <Metric
          label="AWS billed cost"
          value="Not connected"
          sub="No billing data or live pricing source"
          icon={Database}
          tone="amber"
        />
      </div>
      <section className="glass panel">
        <PanelTitle
          title="Transparent cost scenario"
          detail="Enter your own USD prices; this is an estimate, never an AWS bill"
        />
        <form
          className="cost-form"
          onSubmit={(e) => {
            e.preventDefault();
            estimate.mutate();
          }}
        >
          <label>
            Node count
            <input
              type="number"
              min={0}
              max={100}
              value={nodes}
              onChange={(e) => setNodes(Number(e.target.value))}
            />
          </label>
          <label>
            Node price (USD/hour)
            <input
              type="number"
              min={0}
              max={100}
              step="0.001"
              value={hourly}
              onChange={(e) => setHourly(Number(e.target.value))}
            />
          </label>
          <label>
            Cluster fee (USD/hour)
            <input
              type="number"
              min={0}
              max={100}
              step="0.001"
              value={cluster}
              onChange={(e) => setCluster(Number(e.target.value))}
            />
          </label>
          <label>
            Other services (USD/month)
            <input
              type="number"
              min={0}
              max={100000}
              step="0.01"
              value={other}
              onChange={(e) => setOther(Number(e.target.value))}
            />
          </label>
          <Button disabled={estimate.isPending}>
            Calculate scenario <ArrowRight size={15} />
          </Button>
        </form>
        {estimate.data && (
          <div className="cost-result" role="status">
            <div>
              <span>YOUR SCENARIO · 730 HOURS</span>
              <strong>
                $
                {estimate.data.monthly.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
                <small>/month</small>
              </strong>
            </div>
            <p>
              Excludes tax, transfer, credits and services you did not enter.
              Local kind resources do not imply an AWS charge.
            </p>
          </div>
        )}
        {estimate.isError && (
          <p role="alert" className="error-text">
            {estimate.error.message}
          </p>
        )}
      </section>
    </>
  );
}

export function SettingsView({
  session,
  preferences,
}: {
  session: Session;
  preferences?: Preferences;
}) {
  const client = useQueryClient();
  const [refresh, setRefresh] = useState(preferences?.refresh_seconds ?? 15);
  const [compact, setCompact] = useState(preferences?.compact_tables ?? false);
  const [timezone, setTimezone] = useState<"UTC" | "local">(
    preferences?.timezone ?? "UTC",
  );
  const mutation = useMutation({
    mutationFn: () =>
      operations.savePreferences({
        refresh_seconds: refresh,
        compact_tables: compact,
        timezone,
      }),
    onSuccess: () => {
      try {
        localStorage.setItem("sentinel-event-timezone", timezone);
      } catch {
        /* UTC fallback */
      }
      void client.invalidateQueries({ queryKey: ["ops"] });
    },
  });
  return (
    <div className="two-column">
      <section className="glass panel">
        <PanelTitle
          title="Workspace preferences"
          detail="Saved per authenticated user in PostgreSQL"
        />
        <form
          className="stack-form"
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <label>
            Polling interval
            <select
              value={refresh}
              onChange={(e) => setRefresh(Number(e.target.value))}
            >
              <option value={5}>5 seconds</option>
              <option value={15}>15 seconds</option>
              <option value={30}>30 seconds</option>
              <option value={60}>60 seconds</option>
            </select>
          </label>
          <label>
            Event timestamp timezone
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value as "UTC" | "local")}
            >
              <option value="UTC">UTC</option>
              <option value="local">Browser local time</option>
            </select>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={compact}
              onChange={(e) => setCompact(e.target.checked)}
            />
            Compact inventory tables
          </label>
          <p className="muted">
            Motion follows your system reduced-motion setting. The workspace
            uses an accessible dark theme.
          </p>
          <Button disabled={mutation.isPending}>Save preferences</Button>
          {mutation.isSuccess && (
            <p role="status" className="success-text">
              Preferences saved.
            </p>
          )}
          {mutation.isError && (
            <p role="alert" className="error-text">
              {mutation.error.message}
            </p>
          )}
        </form>
      </section>
      <section className="glass panel">
        <PanelTitle
          title="Identity & access"
          detail="Roles are verified by the API, not chosen in the browser"
        />
        <div className="detail-grid">
          <div>
            <span>Identity</span>
            <strong>{session.name}</strong>
            <code>{session.subject}</code>
          </div>
          <div>
            <span>Authentication</span>
            <Badge value={session.authentication} />
          </div>
          <div>
            <span>Roles</span>
            <strong>{session.roles.join(", ")}</strong>
          </div>
          <div>
            <span>Authorized namespaces</span>
            <strong>{session.namespaces.join(", ")}</strong>
          </div>
        </div>
        <div className="notice">
          <ShieldCheck size={19} />
          <p>
            Approvals and policy edits are checked server-side and rate-limited.
            The browser does not receive Kubernetes credentials or the signing
            key.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={async () => {
            await fetch("/api/auth/logout", { method: "POST" });
            window.location.reload();
          }}
        >
          Sign out
        </Button>
      </section>
    </div>
  );
}
