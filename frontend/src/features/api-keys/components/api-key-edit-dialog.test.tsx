import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createApiKey } from "@/test/mocks/factories";
import { renderWithProviders } from "@/test/utils";
import { ApiKeyEditDialog } from "./api-key-edit-dialog";

describe("SwissAI client-key editing", () => {
  it("round-trips token policy and an empty upstream-key restriction", async () => {
    const user = userEvent.setup(); const submit = vi.fn().mockResolvedValue(undefined);
    const key = createApiKey({ name: "Existing SDK", allowedModels: [], sourceAssignmentScopeEnabled: true, assignedSourceIds: [] });
    renderWithProviders(<ApiKeyEditDialog open busy={false} apiKey={key} onOpenChange={vi.fn()} onSubmit={submit} />);
    expect(screen.getByRole("switch", { name: "Restrict models" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "Restrict allowed SwissAI keys" })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Save client key" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith(expect.objectContaining({ name: "Existing SDK", allowedModels: [], assignedSourceIds: [] })));
  });
});
