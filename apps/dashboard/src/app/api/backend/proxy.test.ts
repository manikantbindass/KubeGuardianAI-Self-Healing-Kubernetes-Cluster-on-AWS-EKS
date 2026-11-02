import type { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./[...path]/route";
afterEach(() => vi.unstubAllGlobals());
const request = new Request("http://localhost/api/backend/health") as NextRequest;
describe("backend proxy", () => {
  it("denies unknown paths without contacting the upstream", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    expect((await GET(request, { params: Promise.resolve({ path: ["arbitrary"] }) })).status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("sanitizes upstream errors and includes request correlation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private host")));
    const response = await GET(request, { params: Promise.resolve({ path: ["health"] }) });
    expect(response.status).toBe(503);
    expect(response.headers.get("X-Correlation-ID")).toBeTruthy();
    expect(await response.text()).not.toContain("private host");
  });
  it("forwards readiness status and disables caching", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ status: "unavailable" }, { status: 503 })));
    const response = await GET(request, { params: Promise.resolve({ path: ["ready"] }) });
    expect(response.status).toBe(503);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  });
});
