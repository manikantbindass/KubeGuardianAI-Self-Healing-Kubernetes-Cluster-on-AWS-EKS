import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { OpsIncident, Resource, Session, View } from "@/lib/operations";
import { IncidentCenter, ResourceDetail } from "./views";
const session: Session = {
  subject: "viewer",
  name: "Viewer",
  roles: ["viewer"],
  authentication: "oidc",
  demo_enabled: false,
  namespaces: ["team-a", "team-b"],
  data_default: "real",
};
const incident: OpsIncident = {
  id: "incident-1",
  namespace: "team-a",
  resource: "checkout",
  source: "kubernetes",
  reason: "OOMKilled",
  summary: "Observed container termination",
  severity: "critical",
  status: "open",
  first_seen: "2026-11-03T00:00:00Z",
  last_seen: "2026-11-03T00:00:00Z",
  occurrences: 1,
  confidence: null,
  confidence_label: "Not calibrated",
  review: null,
};
function resource(
  name: string,
  namespace = "team-a",
  kind: Resource["kind"] = "RemediationAction",
): Resource {
  return {
    id: name,
    kind,
    namespace,
    name,
    uid: name,
    resource_version: "1",
    collected_at: "2026-11-03T00:00:00Z",
    data: {
      spec: {
        kind: "Restart",
        target: { name: "checkout", uid: "target", generation: 1, replicas: 2 },
      },
      status: { phase: "AwaitingApproval" },
    },
  };
}
function view(resources: Resource[]): View {
  return {
    mode: "real",
    generated_at: "2026-11-03T00:00:00Z",
    namespaces: ["team-a", "team-b"],
    resources,
    incidents: [incident],
    anomaly_evidence: [],
    commands: [],
    audit: [],
    summary: {
      nodes: 0,
      pods: 0,
      workloads: 0,
      healthy_workloads: 0,
      unhealthy_workloads: 0,
      active_incidents: 1,
      recoveries: 0,
      awaiting_approval: 1,
    },
    bridge: {
      stale: false,
      limited: false,
      last_collected_at: null,
      resource_limit: 1000,
      source: "Kubernetes bridge",
    },
  };
}
function mount(children: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      {children}
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (
    this: HTMLDialogElement,
  ) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn();
});
describe("operations evidence boundaries", () => {
  it("does not link same-name workloads across namespaces", () => {
    mount(
      <IncidentCenter
        view={view([
          resource("correct-action"),
          resource("other-action", "team-b"),
        ])}
        session={session}
        open={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /OOMKilled Observed/ }));
    expect(
      screen.getByRole("button", { name: /Restart.*correct-action/ }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /other-action/ }),
    ).not.toBeInTheDocument();
  });
  it("shows exact related events, excluding name prefixes and foreign namespaces", () => {
    const workload = resource("checkout", "team-a", "Deployment");
    const event = (
      name: string,
      namespace: string,
      owner: string,
      message: string,
    ): Resource => ({
      ...resource(name, namespace, "Event"),
      data: { owner, message, reason: "Readiness", type: "Warning" },
    });
    mount(
      <ResourceDetail
        resource={workload}
        view={view([
          workload,
          event("correct", "team-a", "checkout", "Exact event"),
          event("wrong-ns", "team-b", "checkout", "Foreign event"),
          event(
            "prefix",
            "team-a",
            "checkout-other",
            "Misleading checkout substring",
          ),
        ])}
        session={session}
        close={vi.fn()}
        refresh={vi.fn()}
      />,
    );
    expect(screen.getByText("Exact event")).toBeInTheDocument();
    expect(screen.queryByText("Foreign event")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Misleading checkout substring"),
    ).not.toBeInTheDocument();
  });
  it("explains read-only access instead of offering an unauthorized approval", () => {
    const action = resource("approval-plan");
    mount(
      <ResourceDetail
        resource={action}
        view={view([action])}
        session={session}
        close={vi.fn()}
        refresh={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/Your role can inspect this plan/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Approve exact plan" }),
    ).not.toBeInTheDocument();
  });
});
