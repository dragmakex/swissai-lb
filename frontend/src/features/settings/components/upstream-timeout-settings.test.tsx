import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createDashboardSettings } from "@/test/mocks/factories";
import { UpstreamTimeoutSettings } from "./upstream-timeout-settings";

const CONNECT = "Connection timeout (seconds)";

describe("SwissAI timeouts", () => {
  it("shows four supported inherited timeouts without bridge, compact or WebSocket controls", () => {
    render(<UpstreamTimeoutSettings settings={createDashboardSettings()} busy={false} onSave={vi.fn()} />);
    expect(screen.getAllByRole("spinbutton")).toHaveLength(4);
    expect(screen.getByLabelText(CONNECT)).toHaveDisplayValue("");
    expect(screen.getByLabelText(CONNECT)).toHaveAttribute("placeholder", "8");
    expect(screen.queryByLabelText(/bridge|compact|websocket/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save timeouts" })).toBeDisabled();
  });

  it("saves only edited fields and the optimistic version", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    const settings = createDashboardSettings();
    render(<UpstreamTimeoutSettings settings={settings} busy={false} onSave={save} />);
    await user.type(screen.getByLabelText(CONNECT), "4");
    await user.click(screen.getByRole("button", { name: "Save timeouts" }));
    expect(save).toHaveBeenCalledWith({ expectedVersion: settings.version, upstreamConnectTimeoutSeconds: 4 });
  });

  it("preserves override provenance and clears an edited override with null", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    const settings = createDashboardSettings({ upstreamConnectTimeoutSeconds: 4,
      provenance: { upstream_connect_timeout_seconds: { source: "dashboard", default: 8, envValue: null } },
    });
    render(<UpstreamTimeoutSettings settings={settings} busy={false} onSave={save} />);
    expect(screen.getByLabelText(CONNECT)).toHaveValue(4);
    await user.clear(screen.getByLabelText(CONNECT));
    await user.click(screen.getByRole("button", { name: "Save timeouts" }));
    expect(save).toHaveBeenCalledWith({ expectedVersion: settings.version, upstreamConnectTimeoutSeconds: null });
  });

  it("does not permit a connection timeout larger than the whole request budget", async () => {
    const user = userEvent.setup();
    render(<UpstreamTimeoutSettings settings={createDashboardSettings()} busy={false} onSave={vi.fn()} />);
    await user.type(screen.getByLabelText(CONNECT), "601");
    expect(screen.getByRole("button", { name: "Save timeouts" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Connection timeout must fit both request budgets");
  });

  it("reports rejected saves without losing the draft", async () => {
    const user = userEvent.setup();
    render(<UpstreamTimeoutSettings settings={createDashboardSettings()} busy={false} onSave={vi.fn().mockRejectedValue(new Error("conflict"))} />);
    await user.type(screen.getByLabelText(CONNECT), "4");
    await user.click(screen.getByRole("button", { name: "Save timeouts" }));
    expect(await screen.findByText("conflict")).toBeInTheDocument();
    expect(screen.getByLabelText(CONNECT)).toHaveValue(4);
  });

  it("disables inputs while a save is pending", () => {
    render(<UpstreamTimeoutSettings settings={createDashboardSettings()} busy onSave={vi.fn()} />);
    expect(screen.getByLabelText(CONNECT)).toBeDisabled();
  });
});
