import { Suspense } from "react";
import { OperationsApp } from "@/components/operations/app";
export default function Home() {
  return (
    <Suspense fallback={<p role="status">Connecting to workspace…</p>}>
      <OperationsApp />
    </Suspense>
  );
}
