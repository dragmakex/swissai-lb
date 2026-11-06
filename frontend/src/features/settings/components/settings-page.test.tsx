import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { ADMIN_PERMISSIONS, GUEST_PERMISSIONS, OPERATOR_PERMISSIONS, createDashboardSettings } from "@/test/mocks/factories";
import { renderWithProviders } from "@/test/utils";
import { SettingsPage } from "./settings-page";

const useSettingsMock = vi.fn();
vi.mock("@/features/settings/hooks/use-settings", () => ({ useSettings: () => useSettingsMock() }));
vi.mock("@/features/settings/components/access/access-card", () => ({ AccessCard: () => <div>Access controls</div> }));
vi.mock("@/features/settings/components/telemetry-settings", () => ({ TelemetrySettings: () => <div>Telemetry consent</div> }));
vi.mock("@/features/api-keys/components/api-keys-section", () => ({
  ApiKeysSection: ({ disabled, policyControlsDisabled }: { disabled: boolean; policyControlsDisabled: boolean }) => <>
    <button disabled={disabled}>Client key controls</button><button disabled={policyControlsDisabled}>Client auth policy</button>
  </>,
}));
vi.mock("@/features/swissai/routing-settings", () => ({
  SwissAIRoutingSettings: ({ disabled }: { disabled: boolean }) => <button disabled={disabled}>Routing controls</button>,
}));
vi.mock("@/features/firewall/components/firewall-section", () => ({
  FirewallSection: ({ disabled }: { disabled: boolean }) => <button disabled={disabled}>Firewall controls</button>,
}));

function state(data = createDashboardSettings(), error: Error | null = null, isFetching = false) {
  const refetch = vi.fn().mockResolvedValue(undefined);
  useSettingsMock.mockReturnValue({
    settingsQuery: { data, error, isFetching, isPending: false, refetch },
    updateSettingsMutation: { isPending: false, error: null, mutateAsync: vi.fn().mockResolvedValue(undefined) },
  });
  return refetch;
}

beforeEach(() => {
  useAuthStore.setState({ permissions: ADMIN_PERMISSIONS, canWrite: true, user: null, passwordSessionActive: false });
  state();
});

describe("SwissAI settings composition", () => {
  it("retains access, client keys, routing, firewall, retention, timeouts and telemetry consent", () => {
    renderWithProviders(<SettingsPage />);
    for (const name of ["Client key controls", "Routing controls", "Firewall controls"]) {
      expect(screen.getByRole("button", { name })).toBeEnabled();
    }
    expect(screen.getByText("Access controls")).toBeInTheDocument();
    expect(screen.getByText("Telemetry consent")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Metadata retention" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Upstream timeouts" })).toBeInTheDocument();
    expect(screen.queryByText(/Sticky sessions|Quota Planner|Session Bridge|OAuth|Upstream Proxy Routing/i)).not.toBeInTheDocument();
  });

  it("keeps security mutations disabled for operators without security:write", () => {
    useAuthStore.setState({ permissions: OPERATOR_PERMISSIONS, canWrite: true });
    renderWithProviders(<SettingsPage />);
    expect(screen.getByRole("button", { name: "Firewall controls" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Client auth policy" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Routing controls" })).toBeEnabled();
  });

  it("hides privileged reads and disables mutations for guests", () => {
    useAuthStore.setState({ permissions: GUEST_PERMISSIONS, canWrite: false });
    renderWithProviders(<SettingsPage />);
    expect(screen.queryByText("Client key controls")).not.toBeInTheDocument();
    expect(screen.queryByText("Access controls")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Firewall controls" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Routing controls" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save retention" })).toBeDisabled();
    expect(screen.getByText(/read-only guest access/)).toBeInTheDocument();
  });

  it("does not infer pool-write permission from an unrelated generic write grant", () => {
    useAuthStore.setState({ permissions: ["read", "write", "dashboard:read:all", "accounts:read:all"], canWrite: true });
    renderWithProviders(<SettingsPage />);
    expect(screen.getByRole("button", { name: "Routing controls" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save retention" })).toBeDisabled();
  });

  it("announces a terminal load failure and retries without leaving an endless skeleton", async () => {
    const user = userEvent.setup();
    const refetch = state();
    const current = useSettingsMock();
    current.settingsQuery.data = undefined;
    current.settingsQuery.error = new Error("settings unavailable");
    renderWithProviders(<SettingsPage />);
    expect(screen.getByRole("alert")).toHaveTextContent("settings unavailable");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledOnce();
  });

  it("preserves cached controls during a refetch failure", () => {
    state(createDashboardSettings(), new Error("refresh unavailable"), true);
    renderWithProviders(<SettingsPage />);
    expect(screen.getByText("Access controls")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeDisabled();
  });

  it("honors the retained firewall deep link without a dead Advanced expander", () => {
    const scroll = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scroll });
    window.history.pushState({}, "", "/settings?advanced=1#firewall");
    renderWithProviders(<SettingsPage />);
    expect(scroll).toHaveBeenCalled();
    expect(document.getElementById("firewall")).not.toBeNull();
    expect(screen.queryByRole("button", { name: /Show advanced/i })).not.toBeInTheDocument();
    window.history.pushState({}, "", "/");
  });
});
