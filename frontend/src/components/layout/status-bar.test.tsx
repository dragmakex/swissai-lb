import { screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { ADMIN_PERMISSIONS } from "@/test/mocks/factories";
import { StatusBar } from "@/components/layout/status-bar";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

describe("SwissAI status bar", () => {
  beforeEach(() => useAuthStore.setState({ initialized: true, authenticated: true, role: "admin", permissions: ADMIN_PERMISSIONS }));
  it("shows actual pool routing, readiness and unknown pricing", async () => {
    renderWithProviders(<StatusBar />);
    expect(await screen.findByText("Service: Ready")).toBeInTheDocument();
    expect(await screen.findByText("Routing: least inflight")).toBeInTheDocument();
    expect(screen.getByText("SwissAI pricing: unknown")).toBeInTheDocument();
    expect(screen.queryByText(/capacity weighted|weekly reset|usage synced/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upstream codex-lb" })).toHaveAttribute("href", "https://github.com/Soju06/codex-lb");
  });
  it("reports unready infrastructure without pretending it is an upstream quota outage", async () => {
    server.use(http.get("/health/ready", () => HttpResponse.json({ detail: "unavailable" }, { status: 503 })));
    renderWithProviders(<StatusBar />);
    expect(await screen.findByText("Service: Not ready")).toBeInTheDocument();
    expect(screen.queryByText(/quota exceeded/i)).not.toBeInTheDocument();
  });
});
