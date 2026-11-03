"use client";

import { useId } from "react";
import { download, type Series } from "@/lib/operations";
import { Button } from "@/components/ui/button";

export function TimeChart({
  title,
  series,
  unit,
  color = "#48c8df",
  error,
  loading,
}: {
  title: string;
  series?: Series;
  unit: string;
  color?: string;
  error?: boolean;
  loading?: boolean;
}) {
  const gradient = useId().replaceAll(":", "");
  const data = series?.points ?? [];
  const max = Math.max(...data.map((p) => p[1]), 0.001) * 1.15;
  const format = (v: number) =>
    unit === "GB"
      ? `${(v / 1e9).toFixed(1)}`
      : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  const points = data
    .map(
      (p, i) =>
        `${48 + (i / Math.max(1, data.length - 1)) * 672},${172 - (p[1] / max) * 140}`,
    )
    .join(" ");
  return (
    <section className="glass panel chart-panel" aria-label={title}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          <p>
            {loading
              ? "Fetching telemetry"
              : error
                ? "Source unavailable"
                : series?.source === "synthetic"
                  ? "Synthetic demonstration"
                  : "Prometheus · observed samples"}
          </p>
        </div>
        <span className="chart-value">
          {data.length ? format(data.at(-1)![1]) : "—"}
          <small>{unit}</small>
        </span>
      </div>
      {data.length ? (
        <>
          <svg
            viewBox="0 0 744 208"
            role="img"
            aria-label={`${title}, ${data.length} samples, latest ${format(data.at(-1)![1])} ${unit}`}
            className="time-chart"
          >
            <defs>
              <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity=".22" />
                <stop offset="100%" stopColor={color} stopOpacity="0" />
              </linearGradient>
            </defs>
            {[0, 1, 2, 3].map((i) => (
              <g key={i}>
                <line
                  x1="48"
                  x2="720"
                  y1={32 + i * 47}
                  y2={32 + i * 47}
                  stroke="#263345"
                  strokeDasharray="3 5"
                />
                <text x="0" y={36 + i * 47} fill="#a0afc4" fontSize="11">
                  {format(max * (1 - i / 3))}
                </text>
              </g>
            ))}
            <polygon
              points={`48,172 ${points} 720,172`}
              fill={`url(#${gradient})`}
            />
            <polyline
              points={points}
              fill="none"
              stroke={color}
              strokeWidth="2.4"
              strokeLinejoin="round"
            />
            {[0, 0.25, 0.5, 0.75, 1].map((fraction, i) => (
              <text
                key={i}
                x={48 + fraction * 672}
                y="199"
                textAnchor={i === 0 ? "start" : i === 4 ? "end" : "middle"}
                fill="#a0afc4"
                fontSize="11"
              >
                {new Date(
                  data[Math.round(fraction * (data.length - 1))][0] * 1000,
                ).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </text>
            ))}
          </svg>
          <details className="chart-data">
            <summary>View chart data</summary>
            <Button
              variant="outline"
              onClick={() =>
                download(
                  `${title.toLowerCase().replaceAll(" ", "-")}.csv`,
                  `timestamp,value,unit\n${data.map((p) => `${new Date(p[0] * 1000).toISOString()},${p[1]},${unit}`).join("\n")}`,
                  "text/csv",
                )
              }
            >
              Export CSV
            </Button>
            <div className="table-scroll">
              <table>
                <caption className="sr-only">{title} values</caption>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Value ({unit})</th>
                  </tr>
                </thead>
                <tbody>
                  {data.slice(-12).map((p, i) => (
                    <tr key={i}>
                      <td>{new Date(p[0] * 1000).toISOString()}</td>
                      <td>{format(p[1])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <div className={loading ? "chart-empty skeleton" : "chart-empty"}>
          <span>
            {loading
              ? "Loading observed samples…"
              : error
                ? "Telemetry source is offline"
                : "No samples in this time window"}
          </span>
          <p>
            {error
              ? "Persisted incidents and operator evidence remain available."
              : "Charts appear when the selected telemetry source has data."}
          </p>
        </div>
      )}
    </section>
  );
}

export function SeverityChart({
  incidents,
}: {
  incidents: { severity: string }[];
}) {
  const entries = [
    ["critical", "#fa718b"],
    ["warning", "#f3bb63"],
    ["info", "#65a8fa"],
  ];
  const total = incidents.length;
  let cursor = 0;
  const segments = entries.map(([name, color]) => {
    const count = incidents.filter((i) => i.severity === name).length;
    const start = cursor;
    cursor += (count / Math.max(1, total)) * 100;
    return { name, color, count, start, end: cursor };
  });
  const background = total
    ? `conic-gradient(${segments.map((s) => `${s.color} ${s.start}% ${s.end}%`).join(",")})`
    : "#253146";
  return (
    <section className="glass panel severity-panel">
      <div className="panel-heading">
        <div>
          <h2>Incident distribution</h2>
          <p>Severity of persisted records</p>
        </div>
        <span className="tiny-label">{total} total</span>
      </div>
      <div className="severity-body">
        <div
          className="donut"
          style={{ background }}
          role="img"
          aria-label={segments.map((s) => `${s.count} ${s.name}`).join(", ")}
        >
          <div>
            <strong>{total}</strong>
            <span>INCIDENTS</span>
          </div>
        </div>
        <ul>
          {segments.map((s) => (
            <li key={s.name}>
              <span className="legend-dot" style={{ background: s.color }} />
              <span className="capitalize">{s.name}</span>
              <strong>{s.count}</strong>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
