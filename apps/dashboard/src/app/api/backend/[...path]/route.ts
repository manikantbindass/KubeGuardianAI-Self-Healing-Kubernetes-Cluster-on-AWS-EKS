import type { NextRequest } from "next/server";
import { sameOrigin, sessionToken } from "@/lib/server-auth";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };
async function proxy(request: NextRequest, context: Context) {
  const path = (await context.params).path.join("/");
  const legacy =
    /^(health|ready|version|incidents|telemetry\/health|metrics\/(cpu|memory|restarts|request_rate|error_rate)|jobs|jobs\/[a-fA-F0-9-]{36})$/.test(
      path,
    );
  const operational =
    /^ops\/(session|view|preferences|stream|model|resources\/[a-f0-9]{64}\/logs|metrics\/(cpu|memory|latency|requests)|cost-estimate|actions\/[a-f0-9]{64}\/decision|policies\/[a-f0-9]{64}|incidents\/[a-fA-F0-9-]{36}\/review)$/.test(
      path,
    );
  const postAllowed =
    path === "jobs" ||
    /^ops\/(preferences|cost-estimate|actions\/[a-f0-9]{64}\/decision|policies\/[a-f0-9]{64}|incidents\/[a-fA-F0-9-]{36}\/review)$/.test(
      path,
    );
  if ((!legacy && !operational) || (request.method === "POST" && !postAllowed))
    return Response.json({ error: "Unknown route" }, { status: 404 });
  const token = sessionToken(request);
  if (
    request.method === "POST" &&
    (operational || token) &&
    !sameOrigin(request)
  )
    return Response.json(
      { error: { message: "Same-origin mutation required" } },
      { status: 403 },
    );
  const correlationId = crypto.randomUUID();
  try {
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && body.length > 8192)
      return Response.json({ error: "Payload too large" }, { status: 413 });
    const target = new URL(
      `/api/v1/${path}`,
      process.env.API_BASE_URL ?? "http://127.0.0.1:8000",
    );
    for (const [key, value] of new URL(request.url).searchParams) {
      if (
        !["mode", "namespace", "minutes", "after"].includes(key) ||
        value.length > 128
      )
        return Response.json({ error: "Unsupported query" }, { status: 400 });
      target.searchParams.set(key, value);
    }
    const streaming = path === "ops/stream";
    const upstream = await fetch(target, {
      method: request.method,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(streaming ? 65000 : 6500),
      headers: {
        "Content-Type": "application/json",
        "X-Correlation-ID": correlationId,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(streaming && request.headers.get("Last-Event-ID")
          ? { "Last-Event-ID": request.headers.get("Last-Event-ID")! }
          : {}),
      },
    });
    return new Response(
      streaming && upstream.ok ? upstream.body : await upstream.text(),
      {
        status: upstream.status,
        headers: {
          "Content-Type":
            streaming && upstream.ok ? "text/event-stream" : "application/json",
          "Cache-Control": "no-store",
          "X-Accel-Buffering": "no",
          "X-Correlation-ID":
            upstream.headers.get("X-Correlation-ID") ?? correlationId,
        },
      },
    );
  } catch {
    return Response.json(
      {
        error: {
          code: "upstream_unavailable",
          message: "Backend is unavailable.",
        },
        correlation_id: correlationId,
      },
      {
        status: 503,
        headers: {
          "Cache-Control": "no-store",
          "X-Correlation-ID": correlationId,
        },
      },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
