import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { SwissAIKeysPage } from "@/features/swissai/keys-page";
import { SwissAIOverview } from "@/features/swissai/pool-overview";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { ADMIN_PERMISSIONS, GUEST_PERMISSIONS } from "@/test/mocks/factories";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

const key = { id: "sak_test", name: "Research A", keyPrefix: "sk-rc-…0000", status: "active", enabled: true,
  cooldownUntil: null, failureReason: null, maxConcurrency: 4, inFlight: 0, lastSuccessAt: null,
  lastFailureAt: null, createdAt: "2026-10-28T00:00:00Z" };

describe("SwissAI key management", () => {
  beforeEach(() => useAuthStore.setState({ initialized: true, authenticated: true, role: "admin", permissions: ADMIN_PERMISSIONS }));
  it("adds a credential using the upstream dialog primitives and clears the secret form", async () => {
    const user = userEvent.setup(); let stored = false;
    server.use(http.get("/api/swissai-keys", () => HttpResponse.json(stored ? [key] : [])),
      http.post("/api/swissai-keys", async ({ request }) => {
        expect(await request.json()).toEqual({ name: "Research A", apiKey: "sk-rc-test-fake-0000", maxConcurrency: 4 });
        stored = true; return HttpResponse.json(key, { status: 201 });
      }));
    renderWithProviders(<SwissAIKeysPage />);
    await user.click(await screen.findByRole("button", { name: "Add key" }));
    await user.type(screen.getByLabelText("Label"), "Research A");
    await user.type(screen.getByLabelText("SwissAI key"), "sk-rc-test-fake-0000");
    await user.click(screen.getByRole("button", { name: "Save key" }));
    expect(await screen.findByText("Research A")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByLabelText("SwissAI key")).not.toBeInTheDocument());
    expect(screen.queryByText("sk-rc-test-fake-0000")).not.toBeInTheDocument();
  });
  it.each([
    { tokens: null, label: "Input — · Output —" },
    { tokens: 0, label: "Input 0 · Output 0" },
  ])("shows reported activity without turning $tokens into an invented token value", async ({ tokens, label }) => {
    server.use(http.get("/api/swissai-keys", () => HttpResponse.json([{ ...key, usage: {
      windowStart: "2026-10-22T00:00:00Z", windowEnd: "2026-10-28T12:00:00Z", attempts: 2,
      reportedRequests: tokens == null ? 0 : 1, inputTokens: tokens, outputTokens: tokens,
      dailyRequests: [0, 0, 0, 0, 0, 0, 2],
    } }])));
    renderWithProviders(<SwissAIKeysPage />);
    expect(await screen.findByText(label)).toBeInTheDocument();
    expect(screen.getByText("2 attempted requests · 7 UTC days")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Seven-day attempted requests: 0, 0, 0, 0, 0, 0, 2" })).toBeInTheDocument();
    expect(screen.getByText(`${tokens == null ? 0 : 1}/2 with reported terminal usage`)).toBeInTheDocument();
  });

  it("does not query key or catalog inventory without key-read permission", async () => {
    useAuthStore.setState({ permissions: ["dashboard:read"], canWrite: false });
    let reads = 0;
    server.use(
      http.get("/api/swissai-keys", () => { reads++; return HttpResponse.json([]); }),
      http.get("/api/swissai/catalog", () => { reads++; return HttpResponse.json({ models: [], ageSeconds: null, lastError: null }); }),
    );
    const { queryClient } = renderWithProviders(<SwissAIOverview />);
    expect(screen.getByText("Pool details require SwissAI key read permission.")).toBeInTheDocument();
    await waitFor(() => expect(queryClient.isFetching()).toBe(0));
    expect(reads).toBe(0);
  });

  it("does not render secret mutations for a read-only dashboard viewer", async () => {
    useAuthStore.setState({ role: "guest", permissions: GUEST_PERMISSIONS });
    server.use(http.get("/api/swissai-keys", () => HttpResponse.json([key])));
    renderWithProviders(<SwissAIKeysPage />);
    expect(await screen.findByText("Research A")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add key" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /pause|probe|edit|delete/i })).not.toBeInTheDocument();
  });
});
