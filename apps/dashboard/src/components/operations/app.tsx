"use client";
/* eslint-disable @next/next/no-html-link-for-pages -- OIDC sign-in requires full document navigation; service health is a separate public surface. */

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpRight,
  Bell,
  Boxes,
  ChevronRight,
  CircleHelp,
  Database,
  FileClock,
  Gauge,
  GitBranch,
  Layers3,
  LayoutDashboard,
  Menu,
  Network,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Workflow,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  download,
  operations,
  OperationsError,
  type Mode,
  type Resource,
  type Section,
} from "@/lib/operations";
import { Dialog, Skeleton, ErrorState } from "./primitives";
import {
  Overview,
  ResourceExplorer,
  MetricsView,
  AnomalyView,
  IncidentCenter,
  ActionCenter,
  PolicyCenter,
  InsightsView,
  AuditView,
  InfrastructureView,
  SettingsView,
  ResourceDetail,
} from "./views";

export const navigation = [
  {
    section: "overview",
    title: "Overview",
    icon: LayoutDashboard,
    group: "WORKSPACE",
  },
  {
    section: "explorer",
    title: "Cluster Explorer",
    icon: Network,
    group: "WORKSPACE",
  },
  {
    section: "workloads",
    title: "Nodes and Workloads",
    icon: Boxes,
    group: "WORKSPACE",
  },
  {
    section: "metrics",
    title: "Live Metrics",
    icon: Activity,
    group: "WORKSPACE",
  },
  {
    section: "anomalies",
    title: "AI Anomaly Detection",
    icon: Sparkles,
    group: "INTELLIGENCE",
  },
  {
    section: "incidents",
    title: "Incident Center",
    icon: TriangleAlert,
    group: "INTELLIGENCE",
  },
  {
    section: "actions",
    title: "Self-Healing Actions",
    icon: Workflow,
    group: "INTELLIGENCE",
  },
  {
    section: "policies",
    title: "Recovery Policies",
    icon: ShieldCheck,
    group: "INTELLIGENCE",
  },
  {
    section: "insights",
    title: "AI Insights",
    icon: GitBranch,
    group: "INTELLIGENCE",
  },
  { section: "audit", title: "Audit Logs", icon: FileClock, group: "PLATFORM" },
  {
    section: "infrastructure",
    title: "Infrastructure and Costs",
    icon: Layers3,
    group: "PLATFORM",
  },
  {
    section: "settings",
    title: "Settings",
    icon: Settings2,
    group: "PLATFORM",
  },
] as const;

const descriptions: Record<Section, string> = {
  overview:
    "Your cluster, in focus. Observe, investigate, and recover with confidence.",
  explorer:
    "Explore the resources and events observed by your Kubernetes bridge.",
  workloads:
    "Readiness, replica availability, and the workloads behind your services.",
  metrics:
    "Observed application and cluster telemetry. Missing data stays missing.",
  anomalies:
    "Explainable detection evidence, model lineage, and distribution shifts.",
  incidents:
    "Investigate signals, affected workloads, and verified recovery evidence.",
  actions:
    "Review exact recovery plans, approvals, verification, and rollback outcomes.",
  policies:
    "Explicit guardrails for what may recover, when, and under whose approval.",
  insights:
    "Evidence-led investigation. Clear observations, without invented root causes.",
  audit:
    "Persistent decision and delivery records, with actor and request traceability.",
  infrastructure:
    "Observed local resources and transparent, user-entered cost scenarios.",
  settings:
    "Your workspace preferences, access roles, and data-source configuration.",
};

function Logo() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32">
        <path
          d="M16 2 28 9v14l-12 7L4 23V9z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
        />
        <path
          d="m4 9 12 7 12-7M16 16v14M10 6l12 7v7l-6 3-6-3v-7l12-7"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.2"
        />
      </svg>
    </span>
  );
}

function Login() {
  const query = useQueryClient();
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const config = useQuery({
    queryKey: ["auth-config"],
    queryFn: async () =>
      (await fetch("/api/auth/config")).json() as Promise<{
        mode: string;
        oidc_configured: boolean;
      }>,
  });
  return (
    <div className="login-screen">
      <div className="login-card glass">
        <div className="login-brand">
          <Logo />
          <span>
            KubeSentinel <b>AI</b>
          </span>
        </div>
        <span className="eyebrow">OPERATIONS, WITH GUARDRAILS</span>
        <h1>
          Connect to your
          <br />
          control plane.
        </h1>
        <p>
          One workspace for Kubernetes health, explainable anomalies, and
          policy-approved recovery.
        </p>
        <div className="login-feature">
          <ShieldCheck size={18} />
          <span>Server-verified access. Real telemetry by default.</span>
        </div>
        {config.data?.mode === "development" ? (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                const response = await fetch("/api/auth/development", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ token }),
                });
                if (!response.ok)
                  throw new Error(
                    "Token was not accepted. Check the configured local token.",
                  );
                setToken("");
                await query.invalidateQueries();
              } catch (err) {
                setError(err instanceof Error ? err.message : "Sign-in failed");
              } finally {
                setBusy(false);
              }
            }}
          >
            <label htmlFor="development-token">Local development token</label>
            <input
              id="development-token"
              type="password"
              autoComplete="current-password"
              required
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Enter your configured token"
            />
            <Button type="submit" disabled={busy || !token}>
              {busy ? "Verifying access…" : "Enter workspace"}
              <ArrowUpRight size={16} />
            </Button>
            <small>Development authentication · trusted local use only</small>
          </form>
        ) : config.data?.oidc_configured ? (
          <a href="/api/auth/login" className="primary-link">
            Sign in with your identity provider <ArrowUpRight size={16} />
          </a>
        ) : (
          <div className="notice">
            <CircleHelp size={20} />
            <div>
              <strong>Identity provider not configured</strong>
              <p>
                Configure OIDC for this installation, or explicitly enable local
                development authentication. No production data is replaced with
                a demo.
              </p>
              <a
                href="https://github.com/manikantbindass/KubeSentinel-AI/blob/feat/phase-07-operations-dashboard/docs/runbooks/operations-dashboard.md"
                target="_blank"
                rel="noreferrer"
              >
                Open setup guide <ArrowUpRight size={13} />
              </a>
            </div>
          </div>
        )}
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <a href="/status" className="login-status">
          View public service health <ChevronRight size={14} />
        </a>
      </div>
      <div className="login-decoration" aria-hidden="true">
        <div />
        <div />
        <div />
        <Network size={100} />
      </div>
    </div>
  );
}

export function OperationsApp({ section = "overview" }: { section?: Section }) {
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const mode: Mode = params.get("mode") === "demo" ? "demo" : "real";
  const namespace = params.get("namespace") ?? "all";
  const [mobile, setMobile] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [detail, setDetail] = useState<Resource | null>(null);
  const [stream, setStream] = useState("polling");
  const session = useQuery({
    queryKey: ["ops", "session"],
    queryFn: operations.session,
    retry: false,
  });
  const preferences = useQuery({
    queryKey: ["ops", "preferences"],
    queryFn: operations.preferences,
    enabled: !!session.data,
  });
  useEffect(() => {
    if (preferences.data) {
      try {
        localStorage.setItem(
          "sentinel-event-timezone",
          preferences.data.timezone,
        );
      } catch {
        /* UTC fallback */
      }
    }
  }, [preferences.data]);
  const view = useQuery({
    queryKey: ["ops", "view", mode, namespace],
    queryFn: () => operations.view(mode, namespace),
    enabled: !!session.data,
    refetchInterval: (preferences.data?.refresh_seconds ?? 15) * 1000,
    retry: 1,
  });
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    if (!session.data || typeof EventSource === "undefined") return;
    const events = new EventSource(`/api/backend/ops/stream?mode=${mode}`);
    events.onopen = () => setStream("live");
    events.onerror = () => setStream("reconnecting");
    events.addEventListener("update", () => {
      void queryClient.invalidateQueries({ queryKey: ["ops", "view"] });
    });
    return () => events.close();
  }, [session.data, mode, queryClient]);
  const link = (target: Section) =>
    `${target === "overview" ? "/" : `/${target}`}?mode=${mode}&namespace=${encodeURIComponent(namespace)}`;
  const go = (target: Section) => {
    setMobile(false);
    router.push(link(target));
  };
  const choose = (key: string, value: string) => {
    const next = new URLSearchParams(params.toString());
    next.set(key, value);
    router.replace(`${pathname}?${next}`);
  };
  const nav = (
    <nav aria-label="Main navigation">
      {navigation.map((item, i) => (
        <div key={item.section}>
          {(i === 0 || navigation[i - 1].group !== item.group) && (
            <p className="nav-group">{item.group}</p>
          )}
          <Link
            href={link(item.section)}
            aria-current={section === item.section ? "page" : undefined}
            onClick={() => setMobile(false)}
            title={item.title}
            className={
              section === item.section ? "nav-item active" : "nav-item"
            }
          >
            <item.icon size={18} aria-hidden="true" />
            <span>{item.title}</span>
            {item.section === "incidents" &&
              !!view.data?.summary.active_incidents && (
                <b className="nav-count">
                  {view.data.summary.active_incidents}
                </b>
              )}
          </Link>
        </div>
      ))}
    </nav>
  );
  if (session.isPending)
    return (
      <div className="boot-screen">
        <Logo />
        <p role="status">Connecting to your workspace…</p>
      </div>
    );
  if (!session.data) return <Login />;
  const title =
    navigation.find((item) => item.section === section)?.title ?? "Overview";
  const data = view.data;
  return (
    <div className="operations-root">
      <a href="#operations-main" className="skip-link">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link
          href={link("overview")}
          className="brand"
          aria-label="KubeSentinel AI overview"
        >
          <Logo />
          <span>
            KubeSentinel <b>AI</b>
            <small>INTELLIGENT OPERATIONS</small>
          </span>
        </Link>
        {nav}
        <div className="sidebar-bottom">
          <div className="scope-lock">
            <ShieldCheck size={17} />
            <div>
              <strong>Policy guarded</strong>
              <span>Execution requires explicit consent</span>
            </div>
          </div>
          <a href="/status" className="nav-item" aria-label="Service health">
            <Gauge size={18} />
            <span>Service health</span>
            <ArrowUpRight size={13} />
          </a>
          <button className="profile" onClick={() => go("settings")}>
            <span className="avatar">
              {session.data.name.slice(0, 2).toUpperCase()}
            </span>
            <span>
              <strong>{session.data.name}</strong>
              <small>
                {session.data.roles.includes("admin")
                  ? "Administrator"
                  : session.data.roles.join(" · ")}
              </small>
            </span>
            <Settings2 size={15} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-nav"
              aria-label="Open navigation"
              aria-expanded={mobile}
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <span className="desktop-label">Workspace</span>
            <ChevronRight size={14} className="desktop-label" />
            <strong>{title}</strong>
          </div>
          <div className="topbar-controls">
            <button
              className="global-search"
              aria-label="Search workspace"
              onClick={() => setSearchOpen(true)}
            >
              <Search size={16} />
              <span>Search workspace</span>
              <kbd>Ctrl K</kbd>
            </button>
            <span className="cluster-pill">
              <Network size={14} />
              <span>Local Kubernetes</span>
            </span>
            <button
              className="icon-button notification"
              aria-label={`Open incident center, ${data?.summary.active_incidents ?? 0} active incidents`}
              onClick={() => go("incidents")}
            >
              <Bell size={18} />
              {!!data?.summary.active_incidents && <i />}
            </button>
          </div>
        </header>
        <main id="operations-main" className="main-content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">
                <span className="status-dot" /> KUBERNETES CONTROL PLANE
              </p>
              <h1>{title}</h1>
              <p className="page-description">{descriptions[section]}</p>
            </div>
            <div className="heading-actions">
              <Button
                variant="outline"
                onClick={() =>
                  void queryClient.invalidateQueries({ queryKey: ["ops"] })
                }
                aria-label="Refresh workspace"
                disabled={view.isFetching}
              >
                <RefreshCw
                  size={15}
                  className={view.isFetching ? "spin" : ""}
                />
                <span>Refresh</span>
              </Button>
              <Button
                onClick={() =>
                  data &&
                  download(
                    `kubesentinel-${mode}-report.json`,
                    JSON.stringify(data, null, 2),
                  )
                }
                disabled={!data}
              >
                <ArrowDownToLine size={15} />
                Export report
              </Button>
            </div>
          </div>
          <div className="filter-bar">
            <div className="filter-controls">
              <label>
                <span>Namespace</span>
                <select
                  aria-label="Namespace filter"
                  value={namespace}
                  onChange={(e) => choose("namespace", e.target.value)}
                >
                  <option value="all">All authorized namespaces</option>
                  {session.data.namespaces.map((ns) => (
                    <option key={ns}>{ns}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Data source</span>
                <select
                  aria-label="Data mode"
                  value={mode}
                  onChange={(e) => choose("mode", e.target.value)}
                >
                  <option value="real">Real API</option>
                  {session.data.demo_enabled && (
                    <option value="demo">Synthetic demo</option>
                  )}
                </select>
              </label>
            </div>
            <span
              className={`stream-status ${stream === "live" ? "live" : ""}`}
            >
              <span />
              {stream === "live"
                ? "Live updates"
                : stream === "reconnecting"
                  ? "Reconnecting · polling active"
                  : "Polling updates"}
            </span>
          </div>
          {mode === "demo" && (
            <div className="demo-banner" role="status">
              <Sparkles size={17} />
              <strong>Synthetic demonstration</strong>
              <span>
                Every chart and resource in this mode is synthetic. Decisions
                are recorded for demonstration and never sent to a cluster.
              </span>
            </div>
          )}
          {data?.bridge.limited && (
            <div className="notice" role="status">
              Collection is bounded or truncated. Counts describe the visible
              subset; cluster-wide health is not established.
            </div>
          )}
          {data?.bridge.stale && mode === "real" && (
            <div className="notice">
              <Database size={18} />
              <div>
                <strong>
                  {data.bridge.last_collected_at
                    ? "Cluster collection is stale"
                    : "Kubernetes bridge not connected"}
                </strong>
                <p>
                  {data.bridge.last_collected_at
                    ? "Showing last observed records. Live decisions require a fresh resource version."
                    : "Connect the scoped bridge to populate nodes, workloads, recovery actions and policies. Persisted incidents remain available."}
                </p>
              </div>
            </div>
          )}
          {view.isPending ? (
            <Skeleton />
          ) : view.isError ? (
            <ErrorState
              message={
                view.error instanceof OperationsError
                  ? view.error.message
                  : "The API is offline. No demonstration data has been substituted."
              }
              retry={() => void view.refetch()}
            />
          ) : (
            data && (
              <>
                {section === "overview" && (
                  <Overview view={data} mode={mode} go={go} open={setDetail} />
                )}{" "}
                {(section === "explorer" || section === "workloads") && (
                  <ResourceExplorer
                    view={data}
                    open={setDetail}
                    dense={preferences.data?.compact_tables}
                  />
                )}{" "}
                {section === "metrics" && <MetricsView mode={mode} />}{" "}
                {section === "anomalies" && <AnomalyView view={data} />}{" "}
                {section === "incidents" && (
                  <IncidentCenter
                    view={data}
                    session={session.data}
                    open={setDetail}
                  />
                )}{" "}
                {section === "actions" && (
                  <ActionCenter
                    view={data}
                    session={session.data}
                    open={setDetail}
                  />
                )}{" "}
                {section === "policies" && (
                  <PolicyCenter view={data} session={session.data} />
                )}{" "}
                {section === "insights" && <InsightsView view={data} go={go} />}{" "}
                {section === "audit" && <AuditView view={data} />}{" "}
                {section === "infrastructure" && (
                  <InfrastructureView view={data} />
                )}{" "}
                {section === "settings" &&
                  (preferences.isPending ? (
                    <Skeleton />
                  ) : preferences.isError ? (
                    <ErrorState
                      message="Unable to load saved preferences"
                      retry={() => void preferences.refetch()}
                    />
                  ) : (
                    <SettingsView
                      session={session.data}
                      preferences={preferences.data}
                    />
                  ))}
              </>
            )
          )}
          <footer className="workspace-footer">
            <span>
              <ShieldCheck size={13} />
              KubeSentinel AI · Evidence before action
            </span>
            <span>
              {mode === "demo" ? "SYNTHETIC MODE" : "REAL API MODE"} ·{" "}
              {data
                ? `Updated ${new Date(data.generated_at).toLocaleTimeString()}`
                : "Waiting for API"}
            </span>
          </footer>
        </main>
      </div>
      {mobile && (
        <Dialog title="Workspace navigation" close={() => setMobile(false)}>
          {nav}
        </Dialog>
      )}
      {searchOpen && (
        <Dialog title="Search workspace" close={() => setSearchOpen(false)}>
          <label className="search-field modal-search">
            <Search size={18} />
            <span className="sr-only">Search all resources</span>
            <input
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search names, namespaces, kinds…"
            />
          </label>
          <div className="search-results">
            {(data?.resources ?? [])
              .filter((r) =>
                `${r.name} ${r.kind} ${r.namespace}`
                  .toLowerCase()
                  .includes(search.toLowerCase()),
              )
              .slice(0, 12)
              .map((r) => (
                <button
                  key={r.id}
                  onClick={() => {
                    setDetail(r);
                    setSearchOpen(false);
                  }}
                >
                  <Boxes size={18} />
                  <span>
                    <strong>{r.name}</strong>
                    <small>
                      {r.kind} · {r.namespace || "cluster"}
                    </small>
                  </span>
                  <ChevronRight size={16} />
                </button>
              ))}
            {!data?.resources.length && (
              <p className="muted">No collected resources to search yet.</p>
            )}
          </div>
        </Dialog>
      )}
      {detail && (
        <ResourceDetail
          resource={detail}
          view={data}
          session={session.data}
          close={() => setDetail(null)}
          refresh={() => {
            setDetail(null);
            go("actions");
          }}
        />
      )}
    </div>
  );
}
