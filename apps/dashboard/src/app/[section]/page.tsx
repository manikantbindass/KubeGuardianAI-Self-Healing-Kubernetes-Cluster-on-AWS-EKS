import { Suspense } from "react";
import { notFound } from "next/navigation";
import { OperationsApp } from "@/components/operations/app";
import type { Section } from "@/lib/operations";
const sections: Section[] = [
  "overview",
  "explorer",
  "workloads",
  "metrics",
  "anomalies",
  "incidents",
  "actions",
  "policies",
  "insights",
  "audit",
  "infrastructure",
  "settings",
];
export default async function Page({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (!sections.includes(section as Section)) notFound();
  return (
    <Suspense fallback={<p role="status">Loading workspace…</p>}>
      <OperationsApp section={section as Section} />
    </Suspense>
  );
}
