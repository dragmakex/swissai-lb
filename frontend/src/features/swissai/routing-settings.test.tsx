import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { ADMIN_PERMISSIONS } from "@/test/mocks/factories";

import { StatusBar } from "@/components/layout/status-bar";
import { SwissAIRoutingSettings } from "@/features/swissai/routing-settings";
import { PoolSettingsSchema, type PoolSettings } from "@/features/swissai/hooks";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

describe("SwissAI routing settings", () => {
  beforeEach(() => useAuthStore.setState({ initialized: true, authenticated: true, role: "admin", permissions: ADMIN_PERMISSIONS }));
  it("preserves the complete settings contract when the footer populates the shared cache first", async () => {
    const view = renderWithProviders(<StatusBar />);
    await screen.findByText("Routing: least inflight");
    view.rerender(<><StatusBar /><SwissAIRoutingSettings disabled={false} /></>);
    expect(screen.getByLabelText("Default maximum concurrency per key")).toHaveValue(4);
    expect(screen.getByLabelText("First-byte timeout (seconds)")).toHaveValue(30);
    expect(screen.getByLabelText("Admission timeout (seconds)")).toHaveValue(10);
    expect(screen.getByLabelText("Maximum queued requests")).toHaveValue(128);
  });

  it("saves all routing fields after changing the shared per-key cap", async () => {
    let saved: PoolSettings | undefined;
    server.use(http.put("/api/swissai/settings", async ({ request }) => {
      const payload = PoolSettingsSchema.parse(await request.json());
      saved = payload;
      return HttpResponse.json(payload);
    }));
    const user = userEvent.setup();
    renderWithProviders(<SwissAIRoutingSettings disabled={false} />);
    const cap = await screen.findByLabelText("Default maximum concurrency per key");
    await user.clear(cap);
    await user.type(cap, "7");
    await user.click(screen.getByRole("button", { name: "Save routing" }));
    await waitFor(() => expect(saved).toEqual({
      strategy: "least_inflight", single_key_id: null, default_max_concurrency: 7,
      first_byte_timeout_seconds: 30, admission_timeout_seconds: 10, max_queue_size: 128,
    }));
  });
});
