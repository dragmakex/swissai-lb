import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { ApiKeyCreateDialog } from "./api-key-create-dialog";

describe("SwissAI client-key creation", () => {
  it("offers model/key scoping and token limits, not subscription or WebSocket controls", () => {
    renderWithProviders(<ApiKeyCreateDialog open busy={false} onOpenChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByRole("switch", { name: "Restrict models" })).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Restrict allowed SwissAI keys" })).toBeInTheDocument();
    expect(screen.queryByText("Apply to codex /model")).not.toBeInTheDocument();
    expect(screen.queryByText(/always websocket/i)).not.toBeInTheDocument();
  });
  it("sends explicit unrestricted nulls by default", async () => {
    const user = userEvent.setup(); const submit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<ApiKeyCreateDialog open busy={false} onOpenChange={vi.fn()} onSubmit={submit} />);
    await user.type(screen.getByLabelText("Name"), "LAN SDK");
    await user.click(screen.getByRole("button", { name: "Save client key" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith(expect.objectContaining({ name: "LAN SDK", allowedModels: null, assignedSourceIds: null })));
  });
  it("preserves empty restrictive lists instead of silently granting all access", async () => {
    const user = userEvent.setup(); const submit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<ApiKeyCreateDialog open busy={false} onOpenChange={vi.fn()} onSubmit={submit} />);
    await user.type(screen.getByLabelText("Name"), "Restricted");
    await user.click(screen.getByRole("switch", { name: "Restrict models" }));
    await user.click(screen.getByRole("switch", { name: "Restrict allowed SwissAI keys" }));
    await user.click(await screen.findByRole("button", { name: "No models selected" }));
    expect(screen.getByRole("menuitemcheckbox", { name: "No models selected" })).toHaveAttribute("aria-checked", "true");
    await user.keyboard("{Escape}");
    await user.click(await screen.findByRole("button", { name: "No upstream keys selected" }));
    expect(screen.getByRole("menuitemcheckbox", { name: "No upstream keys selected" })).toHaveAttribute("aria-checked", "true");
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Save client key" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith(expect.objectContaining({ allowedModels: [], assignedSourceIds: [] })));
  });
});
