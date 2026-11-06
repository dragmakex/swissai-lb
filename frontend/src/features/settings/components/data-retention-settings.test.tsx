import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createDashboardSettings } from "@/test/mocks/factories";
import { DataRetentionSettings } from "./data-retention-settings";

const LABEL = "Retain request, attempt, audit and continuation metadata (days)";

describe("SwissAI metadata retention", () => {
  it("shows inherited retention without exposing bridge or subscription windows", () => {
    render(<DataRetentionSettings settings={createDashboardSettings()} busy={false} onSave={vi.fn()} />);
    expect(screen.getByLabelText(LABEL)).toHaveDisplayValue("");
    expect(screen.queryByLabelText(/usage history|spool/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Prompts, completions and tool arguments are not stored/)).toBeInTheDocument();
  });

  it.each(["0", "30", "3650"])("saves a valid %s-day override without echoing unrelated settings", async value => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    const settings = createDashboardSettings();
    render(<DataRetentionSettings settings={settings} busy={false} onSave={save} />);
    await user.type(screen.getByLabelText(LABEL), value);
    await user.click(screen.getByRole("button", { name: "Save retention" }));
    expect(save).toHaveBeenCalledWith({ expectedVersion: settings.version, requestLogRetentionOverrideDays: Number(value) });
  });

  it("blocks values below the retention floor", async () => {
    const user = userEvent.setup();
    render(<DataRetentionSettings settings={createDashboardSettings()} busy={false} onSave={vi.fn()} />);
    await user.type(screen.getByLabelText(LABEL), "29");
    expect(screen.getByRole("button", { name: "Save retention" })).toBeDisabled();
  });

  it("clears a stored override with an explicit null", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    render(<DataRetentionSettings settings={createDashboardSettings({ requestLogRetentionOverrideDays: 90 })} busy={false} onSave={save} />);
    await user.clear(screen.getByLabelText(LABEL));
    await user.click(screen.getByRole("button", { name: "Save retention" }));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ requestLogRetentionOverrideDays: null }));
  });

  it("keeps the editor and reports a save failure", async () => {
    const user = userEvent.setup();
    render(<DataRetentionSettings settings={createDashboardSettings()} busy={false} onSave={vi.fn().mockRejectedValue(new Error("save unavailable"))} />);
    await user.click(screen.getByRole("button", { name: "Save retention" }));
    await waitFor(() => expect(screen.getByText("save unavailable")).toBeInTheDocument());
    expect(screen.getByLabelText(LABEL)).toBeEnabled();
  });

  it("disables mutation controls while busy", () => {
    render(<DataRetentionSettings settings={createDashboardSettings()} busy onSave={vi.fn()} />);
    expect(screen.getByLabelText(LABEL)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save retention" })).toBeDisabled();
  });
});
