"use client";
import {
  ArrowUpRight,
  Boxes,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import type { Mode, Resource, Section, View } from "@/lib/operations";
import { Badge } from "./primitives";

export function ClusterCanvas({
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
  const workloads = view.resources.filter((r) => r.kind === "Deployment");
  const visible = workloads.slice(0, 6);
  return (
    <>
      <section className="canvas-hero" aria-labelledby="canvas-title">
        <div className="canvas-copy">
          <span className="canvas-kicker">
            <span /> THE INTELLIGENT CLUSTER WORKSPACE
          </span>
          <h2 id="canvas-title">
            Complex systems.
            <br />
            <em>Clear perspective.</em>
          </h2>
          <p>
            Turn cluster signals into understanding. Explore your workloads,
            uncover anomalies, and shape safer recoveries — with evidence at
            every step.
          </p>
          <div className="canvas-actions">
            <button className="canvas-primary" onClick={() => go("explorer")}>
              Explore your cluster <ArrowUpRight size={17} />
            </button>
            <button className="canvas-secondary" onClick={() => go("actions")}>
              Review recovery <Workflow size={16} />
            </button>
          </div>
          <div className="canvas-principles">
            <span>
              <ScanLine size={14} /> Explainable signals
            </span>
            <span>
              <ShieldCheck size={14} /> Human-approved actions
            </span>
          </div>
        </div>
        <div className="cluster-art">
          <div className="art-topline">
            <span>
              <Sparkles size={14} /> CLUSTER CANVAS
            </span>
            <span>
              {mode === "demo"
                ? "SYNTHETIC"
                : view.bridge.stale
                  ? "AWAITING SOURCE"
                  : "COLLECTED"}
            </span>
          </div>
          <svg
            viewBox="0 0 520 320"
            role="img"
            aria-label={`Abstract cluster visualization. ${view.summary.nodes} nodes and ${view.summary.workloads} workloads collected. Geometry is illustrative.`}
          >
            <defs>
              <linearGradient id="canvas-band" x1="0" y1="0" x2="1" y2="1">
                <stop stopColor="#8cffcf" />
                <stop offset=".45" stopColor="#64b8ff" />
                <stop offset="1" stopColor="#c69aff" />
              </linearGradient>
              <radialGradient id="canvas-halo">
                <stop stopColor="#8261c7" stopOpacity=".4" />
                <stop offset="1" stopColor="#17191d" stopOpacity="0" />
              </radialGradient>
            </defs>
            <ellipse
              cx="260"
              cy="166"
              rx="240"
              ry="147"
              fill="url(#canvas-halo)"
            />
            <g className="canvas-orbits" fill="none" stroke="url(#canvas-band)">
              {Array.from({ length: 22 }, (_, i) => (
                <ellipse
                  key={i}
                  cx="260"
                  cy="162"
                  rx={58 + i * 5.8}
                  ry={110 - i * 2.1}
                  transform={`rotate(${i * 8.18} 260 162)`}
                  opacity={0.3 + i * 0.025}
                  strokeWidth=".8"
                />
              ))}
            </g>
            <circle
              cx="260"
              cy="162"
              r="33"
              fill="#151a20"
              stroke="#9bf0ca"
              strokeWidth=".7"
            />
            <path
              d="m260 144 16 9v18l-16 9-16-9v-18zm0 0v18m-16-9 16 9 16-9m-16 9v18"
              fill="none"
              stroke="#a6f1d0"
              strokeWidth="1.2"
            />
            <circle cx="138" cy="98" r="4" fill="#b797ff" />
            <circle cx="383" cy="211" r="4" fill="#8cf0d4" />
          </svg>
          <div className="art-bottomline">
            <span>
              <i /> {view.summary.nodes} NODES · {view.summary.workloads}{" "}
              WORKLOADS
            </span>
            <span>ILLUSTRATIVE GEOMETRY</span>
          </div>
        </div>
      </section>
      <section className="workload-gallery" aria-labelledby="gallery-title">
        <div className="gallery-heading">
          <div>
            <span className="canvas-kicker">YOUR CLUSTER, CURATED</span>
            <h2 id="gallery-title">The workload gallery</h2>
          </div>
          <button className="text-action" onClick={() => go("workloads")}>
            All workloads <ArrowUpRight size={15} />
          </button>
        </div>
        {visible.length ? (
          <div className="gallery-grid">
            {visible.map((r, i) => (
              <button
                className={`workload-art-card art-${i % 4}`}
                key={r.id}
                onClick={() => open(r)}
              >
                <div className="workload-art-cover">
                  <div className="art-stack">
                    <i />
                    <i />
                    <i />
                    <Boxes size={26} />
                  </div>
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  <ArrowUpRight size={16} />
                </div>
                <div className="workload-art-caption">
                  <strong>{r.name}</strong>
                  <span>{r.namespace}</span>
                  <Badge
                    value={r.data.healthy ? "Healthy" : "Needs attention"}
                  />
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="gallery-empty">
            <Boxes size={24} />
            <div>
              <strong>Your canvas is waiting.</strong>
              <p>
                Connect the Kubernetes bridge to see collected workloads here.
                Real mode stays empty until data arrives.
              </p>
            </div>
            <button className="text-action" onClick={() => go("settings")}>
              Connection settings <ArrowUpRight size={15} />
            </button>
          </div>
        )}
      </section>
      <section className="recovery-studio" aria-labelledby="studio-title">
        <div className="gallery-heading">
          <div>
            <span className="canvas-kicker">FROM SIGNAL TO SAFE ACTION</span>
            <h2 id="studio-title">Your recovery toolkit</h2>
          </div>
          <span className="studio-note">
            Observe → understand → approve → verify
          </span>
        </div>
        <div className="studio-grid">
          {[
            {
              step: "01",
              title: "Find the signal",
              text: "Explore actual resource metrics, events, and anomaly evidence.",
              icon: ScanLine,
              section: "anomalies" as Section,
              value: `${view.anomaly_evidence.length} evidence records`,
              tone: "mint",
            },
            {
              step: "02",
              title: "Shape the response",
              text: "Inspect policy guards and the exact plan before giving consent.",
              icon: ShieldCheck,
              section: "actions" as Section,
              value: `${view.summary.awaiting_approval} awaiting approval`,
              tone: "lilac",
            },
            {
              step: "03",
              title: "Verify the outcome",
              text: "Trace operator verification, audit evidence, and rollback results.",
              icon: Workflow,
              section: "audit" as Section,
              value: `${view.summary.recoveries} verified recoveries`,
              tone: "peach",
            },
          ].map((t) => (
            <button
              className={`studio-card ${t.tone}`}
              onClick={() => go(t.section)}
              key={t.step}
            >
              <div>
                <t.icon size={22} />
                <span>{t.step}</span>
              </div>
              <h3>{t.title}</h3>
              <p>{t.text}</p>
              <footer>
                <span>{t.value}</span>
                <ArrowUpRight size={17} />
              </footer>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
