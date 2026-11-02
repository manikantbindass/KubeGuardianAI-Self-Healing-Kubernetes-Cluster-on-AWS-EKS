import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Home from "./page";
import { api, ApiError } from "@/lib/api";

vi.mock("@/lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("@/lib/api")>()), api: { health: vi.fn(), ready: vi.fn(), version: vi.fn(), jobs: vi.fn(), createJob: vi.fn() } }));
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><Home /></QueryClientProvider>);
}
beforeEach(() => {
  vi.mocked(api.health).mockResolvedValue({ status: "ok", service: "kubesentinel-api", version: "0.1.0" });
  vi.mocked(api.ready).mockResolvedValue({ status: "ready", dependencies: { postgresql: "ok", redis: "ok" } });
  vi.mocked(api.version).mockResolvedValue({ version: "0.1.0", api_version: "v1", environment: "local" });
  vi.mocked(api.jobs).mockResolvedValue([]);
});
describe("status page", () => {
  it("shows connected, ready, empty state and accessible navigation", async () => {
    mount();
    expect(await screen.findByText("Backend connected")).toBeInTheDocument();
    expect(await screen.findByText("All dependencies ready")).toBeInTheDocument();
    expect(await screen.findByText(/No greetings yet/)).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your name" })).toBeInTheDocument();
  });
  it("shows loading without declaring health", () => {
    vi.mocked(api.health).mockImplementation(() => new Promise(() => {}));
    mount();
    expect(screen.getByText("Checking backend…")).toBeInTheDocument();
  });
  it("distinguishes offline and readiness failure", async () => {
    vi.mocked(api.health).mockRejectedValue(new TypeError("fetch failed"));
    vi.mocked(api.ready).mockResolvedValue({ status: "unavailable", dependencies: { redis: "unavailable" } });
    mount();
    expect(await screen.findByText("Backend offline")).toBeInTheDocument();
    expect(await screen.findByText("Dependencies unavailable")).toBeInTheDocument();
  });
  it("shows error correlation ID and queues a greeting", async () => {
    vi.mocked(api.health).mockRejectedValue(new ApiError(500, "test-id"));
    vi.mocked(api.createJob).mockResolvedValue({ id: "1", name: "Ada", status: "queued", message: null, created_at: "2026-11-02" });
    mount();
    expect(await screen.findByText("Backend error")).toBeInTheDocument();
    expect(screen.getByText("Request: test-id")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Your name" }), { target: { value: "Ada" } });
    fireEvent.click(screen.getByRole("button", { name: "Queue greeting" }));
    await waitFor(() => expect(api.createJob).toHaveBeenCalledWith("Ada", expect.anything()));
  });
});
