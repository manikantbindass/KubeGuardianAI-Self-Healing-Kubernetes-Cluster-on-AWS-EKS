import { afterEach, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";
import { GET, POST } from "./route";

vi.mock("@/lib/server-auth", () => ({
  sameOrigin: () => true,
  sessionToken: () => "test-access-token",
}));
afterEach(() => vi.unstubAllGlobals());

it("forwards scoped intelligence reads and preserves backend authorization", async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({ explanations: [] }));
  vi.stubGlobal("fetch", fetch);
  const response = await GET(
    new Request(
      "http://localhost/api/backend/ops/intelligence?mode=real&namespace=team-a",
    ) as NextRequest,
    { params: Promise.resolve({ path: ["ops", "intelligence"] }) },
  );
  expect(response.status).toBe(200);
  expect(String(fetch.mock.calls[0][0])).toBe(
    "http://127.0.0.1:8000/api/v1/ops/intelligence?mode=real&namespace=team-a",
  );
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe(
    "Bearer test-access-token",
  );
});

it("does not widen the proxy to internal endpoints or intelligence mutations", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  for (const path of [
    ["ops", "internal", "snapshots"],
    ["ops", "intelligence"],
  ]) {
    const response = await POST(
      new Request("http://localhost/api/backend/" + path.join("/"), {
        method: "POST",
      }) as NextRequest,
      { params: Promise.resolve({ path }) },
    );
    expect(response.status).toBe(404);
  }
  expect(fetch).not.toHaveBeenCalled();
});
