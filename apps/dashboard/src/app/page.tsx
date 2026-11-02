"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";

export default function Home() {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 10000 });
  const ready = useQuery({ queryKey: ["ready"], queryFn: api.ready, refetchInterval: 10000 });
  const version = useQuery({ queryKey: ["version"], queryFn: api.version });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.jobs, refetchInterval: 2000 });
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: api.incidents, refetchInterval: 10000 });
  const create = useMutation({ mutationFn: api.createJob, onSuccess: () => { setName(""); void client.invalidateQueries({ queryKey: ["jobs"] }); } });
  const error = health.error;
  const status = health.isPending ? "Checking backend…" : error ? error instanceof ApiError && error.code !== "upstream_unavailable" ? "Backend error" : "Backend offline" : "Backend connected";

  return (
    <div className="min-h-screen md:grid md:grid-cols-[230px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-primary focus:p-3 focus:text-primary-foreground">Skip to content</a>
      <aside className="border-b border-border p-6 md:border-r md:border-b-0">
        <p className="text-xl font-bold">KubeSentinel <span className="text-primary">AI</span></p>
        <p className="mt-2 text-xs tracking-widest text-muted-foreground">LOCAL CONTROL PLANE</p>
        <nav aria-label="Main navigation" className="mt-8 flex gap-3 md:flex-col">
          <a href="#status" aria-current="page" className="rounded-md bg-muted px-3 py-2 text-sm">System status</a>
          <a href="#jobs" className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Background jobs</a>
        </nav>
        <p className="mt-8 text-xs leading-relaxed text-muted-foreground">Local telemetry foundation<br />No remediation enabled</p>
      </aside>
      <main id="main" className="mx-auto w-full max-w-6xl px-6 py-10 md:px-12">
        <header className="mb-10 flex flex-wrap items-start justify-between gap-5">
          <div><p className="text-sm text-primary">DEVELOPMENT ENVIRONMENT</p><h1 className="mt-3 text-3xl font-bold md:text-4xl">System status</h1><p className="mt-3 text-muted-foreground">Live connectivity, dependency readiness, and durable background work.</p></div>
          <Button variant="outline" onClick={() => void client.invalidateQueries()} disabled={health.isFetching}>Refresh status</Button>
        </header>
        <section id="status" aria-labelledby="connectivity" className="grid gap-5 lg:grid-cols-2">
          <Card><h2 id="connectivity" className="font-semibold">Backend connectivity</h2>
            <div role="status" aria-live="polite" className="mt-5"><p className={`text-xl font-semibold ${error ? "text-amber-300" : "text-primary"}`}>{status}</p>
              <p className="mt-3 text-sm text-muted-foreground">{health.isPending ? "Waiting for the API response." : error ? "Start the backend and check API_BASE_URL, then refresh." : `${health.data.service} · v${health.data.version}`}</p>
              {error instanceof ApiError && error.correlationId && <p className="mt-2 break-all text-xs text-muted-foreground">Request: {error.correlationId}</p>}
            </div>
          </Card>
          <Card><h2 className="font-semibold">Dependency readiness</h2>
            <div role="status" aria-live="polite" className="mt-5">
              {ready.isPending ? <p className="animate-pulse text-muted-foreground">Checking PostgreSQL and Redis…</p> : ready.isError ? <p className="text-amber-300">Readiness unavailable. Check backend connectivity.</p> : <><p className={`text-xl font-semibold ${ready.data.status === "ready" ? "text-emerald-300" : "text-amber-300"}`}>{ready.data.status === "ready" ? "All dependencies ready" : "Dependencies unavailable"}</p><ul className="mt-4 space-y-2 text-sm">{Object.entries(ready.data.dependencies).map(([key, value]) => <li key={key} className="flex justify-between gap-4"><span className="text-muted-foreground">{key}</span><span>{value}</span></li>)}</ul></>}
            </div>
          </Card>
        </section>
        <Card id="jobs" className="mt-6" aria-labelledby="jobs-title">
          <h2 className="text-xl font-semibold">Telemetry incidents</h2>
          <div aria-live="polite" className="my-5">
            {incidents.isPending ? <p>Loading incidents…</p> : incidents.isError ? <p role="alert">Incident store unavailable. Metrics outages do not erase persisted incidents.</p> : incidents.data.length === 0 ? <p className="text-muted-foreground">No incidents recorded. Enable the observability stack to ingest cluster warnings and alerts.</p> : <ul className="divide-y divide-border">{incidents.data.map(incident => <li key={incident.id} className="py-3"><p>{incident.reason} · {incident.severity} · {incident.status}</p><p className="text-sm text-muted-foreground">{incident.source} / {incident.resource}: {incident.summary}</p></li>)}</ul>}
          </div>
          <h2 id="jobs-title" className="text-xl font-semibold">Background greetings</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">Create a greeting to exercise the API, PostgreSQL, Redis, and worker. This demo never performs cluster actions.</p>
          <form className="mt-6 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); if (name.trim()) create.mutate(name.trim()); }}>
            <div className="min-w-48 flex-1"><label htmlFor="name" className="mb-2 block text-sm">Your name</label><input id="name" value={name} onChange={e => setName(e.target.value)} maxLength={80} required className="h-10 w-full rounded-md border border-border bg-background px-3 focus-visible:outline-2 focus-visible:outline-ring" placeholder="Platform engineer" /></div>
            <Button type="submit" disabled={create.isPending || !name.trim()}>{create.isPending ? "Queuing…" : "Queue greeting"}</Button>
          </form>
          {create.isError && <p role="alert" className="mt-4 text-sm text-amber-300">Could not queue a greeting. Check database readiness and retry.</p>}
          <div className="mt-7" aria-live="polite">
            {jobs.isPending ? <p className="animate-pulse text-muted-foreground">Loading recent jobs…</p> : jobs.isError ? <p role="alert" className="text-amber-300">Recent jobs unavailable. Start the database and apply migrations.</p> : jobs.data.length === 0 ? <p className="rounded-md border border-dashed border-border p-6 text-sm text-muted-foreground">No greetings yet. Queue the first one above.</p> : <ul className="divide-y divide-border">{jobs.data.map(job => <li key={job.id} className="flex flex-wrap justify-between gap-3 py-4"><div><p className="text-sm">{job.message ?? `Waiting for the worker to greet ${job.name}…`}</p><p className="mt-1 text-xs text-muted-foreground">{job.id}</p></div><span className="text-xs text-primary">{job.status}</span></li>)}</ul>}
          </div>
        </Card>
        <footer className="mt-8 text-xs leading-relaxed text-muted-foreground">{version.data ? `API ${version.data.api_version} · ${version.data.environment} · v${version.data.version}` : "Version unavailable"} · Telemetry incidents are advisory. Authentication, anomaly models and remediation remain future work.</footer>
      </main>
    </div>
  );
}
