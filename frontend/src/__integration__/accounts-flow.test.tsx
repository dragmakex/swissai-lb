import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "@/App";
import { renderWithProviders } from "@/test/utils";

async function addKey(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(await screen.findByRole("button", { name: "Add key" }));
  const dialog = screen.getByRole("dialog", { name: "Add SwissAI key" });
  await user.type(within(dialog).getByLabelText("Label"), name);
  await user.type(within(dialog).getByLabelText("SwissAI key"), "sk-rc-test-integration-00000001");
  await user.click(within(dialog).getByRole("button", { name: "Save key" }));
  const row = (await screen.findByText(name)).closest("tr");
  if (!row) throw new Error("Expected the created key row");
  return row;
}

describe("SwissAI key management flow", () => {
  it("adds, probes, pauses, resumes and deletes the selected encrypted key", async () => {
    const user = userEvent.setup();
    window.history.pushState({}, "", "/accounts");
    renderWithProviders(<App />);
    expect(await screen.findByRole("heading", { name: "SwissAI Keys" })).toBeInTheDocument();
    const row = await addKey(user, "Integration upstream");
    expect(within(row).getByText("active")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("sk-rc-test-integration-00000001")).not.toBeInTheDocument();
    await user.click(within(row).getByRole("button", { name: "Pause Integration upstream" }));
    await user.click(await within(row).findByRole("button", { name: "Resume Integration upstream" }));
    expect(await within(row).findByRole("button", { name: "Pause Integration upstream" })).toBeInTheDocument();
    await user.click(within(row).getByRole("button", { name: "Probe Integration upstream" }));
    await waitFor(() => expect(within(row).queryByText("Success —")).not.toBeInTheDocument());
    await user.click(within(row).getByRole("button", { name: "Delete Integration upstream" }));
    const confirm = await screen.findByRole("alertdialog", { name: "Delete SwissAI key?" });
    await user.click(within(confirm).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByText("Integration upstream")).not.toBeInTheDocument());
  });

  it("renames an upstream key and refuses to clear its required operator label", async () => {
    const user = userEvent.setup();
    window.history.pushState({}, "", "/accounts");
    renderWithProviders(<App />);
    const row = await addKey(user, "Original upstream");
    await user.click(within(row).getByRole("button", { name: "Edit Original upstream" }));
    const dialog = screen.getByRole("dialog", { name: "Edit SwissAI key" });
    const label = within(dialog).getByLabelText("Label");
    await user.clear(label);
    await user.type(label, "Renamed upstream");
    await user.click(within(dialog).getByRole("button", { name: "Save key" }));
    expect(await screen.findByText("Renamed upstream")).toBeInTheDocument();
    expect(screen.queryByText("Original upstream")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit Renamed upstream" }));
    const reopened = screen.getByRole("dialog", { name: "Edit SwissAI key" });
    await user.clear(within(reopened).getByLabelText("Label"));
    await user.click(within(reopened).getByRole("button", { name: "Save key" }));
    expect(within(reopened).getByLabelText("Label")).toBeInvalid();
    expect(screen.getByText("Renamed upstream")).toBeInTheDocument();
  });
});
