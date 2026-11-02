import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
afterEach(() => vi.unstubAllGlobals());
describe("typed API client", () => {
  it("rejects invalid health contracts", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ status: "ok" })));
    await expect(api.health()).rejects.toThrow("contract");
  });
  it("preserves HTTP status and correlation ID", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({}, { status: 503, headers: { "X-Correlation-ID": "id" } })));
    await expect(api.jobs()).rejects.toEqual(new ApiError(503, "id"));
  });
  it("reads a dependency failure as typed readiness", async () => {
    const body = { status: "unavailable", dependencies: { redis: "unavailable" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(body, { status: 503 })));
    await expect(api.ready()).resolves.toEqual(body);
  });
});
