import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };
async function proxy(request: NextRequest, context: Context) {
  const path = (await context.params).path.join("/");
  const allowed = /^(health|ready|version|incidents|telemetry\/health|metrics\/(cpu|memory|restarts|request_rate|error_rate)|jobs|jobs\/[a-fA-F0-9-]{36})$/.test(path);
  if (!allowed || (request.method === "POST" && path !== "jobs")) return Response.json({ error: "Unknown route" }, { status: 404 });
  const correlationId = crypto.randomUUID();
  try {
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && body.length > 2048) return Response.json({ error: "Payload too large" }, { status: 413 });
    const upstream = await fetch(new URL(`/api/v1/${path}`, process.env.API_BASE_URL ?? "http://127.0.0.1:8000"), {
      method: request.method, body, cache: "no-store", signal: AbortSignal.timeout(6500),
      headers: { "Content-Type": "application/json", "X-Correlation-ID": correlationId },
    });
    return new Response(await upstream.text(), { status: upstream.status, headers: {
      "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Correlation-ID": upstream.headers.get("X-Correlation-ID") ?? correlationId,
    } });
  } catch {
    return Response.json({ error: { code: "upstream_unavailable", message: "Backend is unavailable." }, correlation_id: correlationId },
      { status: 503, headers: { "Cache-Control": "no-store", "X-Correlation-ID": correlationId } });
  }
}
export const GET = proxy;
export const POST = proxy;
