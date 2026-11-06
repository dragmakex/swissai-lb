import { HttpResponse, http } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import App from "@/App";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import {
  ADMIN_PERMISSIONS,
  GUEST_PERMISSIONS,
  createDashboardAuthSession,
  createUpstreamProxyAdmin,
} from "@/test/mocks/factories";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

// Reads the backend answers with 403 `permission_required` for principals
// without the coarse `write` alias (the built-in guest). The guest UI must
// never issue them.
const RESTRICTED_PATHS = [
  "/api/api-keys/",
  "/api/api-keys",
  "/api/settings/upstream-proxy",
  "/api/settings/runtime/connect-address",
  "/api/sticky-sessions",
  "/api/oauth/status",
];

const guestSession = createDashboardAuthSession({
  authenticated: true,
  passwordRequired: false,
  totpConfigured: false,
  role: "guest",
  permissions: GUEST_PERMISSIONS,
  guestAccessEnabled: true,
  guestPasswordRequired: false,
});

const swissaiKeys = [{
  id: "sak_primary", name: "Shared teaching key", keyPrefix: "sk-rc-…demo", status: "active", enabled: true,
  cooldownUntil: null, failureReason: null, maxConcurrency: 4, inFlight: 0,
  lastSuccessAt: null, lastFailureAt: null, createdAt: "2026-10-28T00:00:00Z",
}];

function spyRequestPaths(): string[] {
  const paths: string[] = [];
  server.events.on("request:start", ({ request }) => {
    paths.push(new URL(request.url).pathname);
  });
  return paths;
}

function spyRequestUrls(): URL[] {
  const urls: URL[] = [];
  server.events.on("request:start", ({ request }) => {
    urls.push(new URL(request.url));
  });
  return urls;
}

function requestLogUrls(urls: URL[]): URL[] {
  return urls.filter((url) => url.pathname === "/api/request-logs" || url.pathname === "/api/request-logs/options");
}

function restrictedRequests(paths: string[]): string[] {
  return paths.filter((path) => RESTRICTED_PATHS.includes(path) || path.startsWith("/api/api-keys/"));
}

function useGuestSession() {
  server.use(
    http.get("/api/dashboard-auth/session", () => HttpResponse.json(guestSession)),
    http.get("/api/swissai-keys", () => HttpResponse.json(swissaiKeys)),
  );
  useAuthStore.setState({
    authenticated: true,
    passwordRequired: false,
    role: "guest",
    permissions: GUEST_PERMISSIONS,
    canWrite: false,
    guestAccessEnabled: true,
    guestPasswordRequired: false,
    initialized: true,
  });
}

describe("guest restricted surfaces integration", () => {
  beforeEach(() => {
    useAuthStore.setState({ role: "admin", permissions: ADMIN_PERMISSIONS, canWrite: true, initialized: false });
  });

  afterEach(() => {
    server.events.removeAllListeners();
    useAuthStore.setState({ role: "admin", permissions: ADMIN_PERMISSIONS, canWrite: true, initialized: false });
  });

  it("shows the administrator-only notice on /apis without requesting API keys", async () => {
    useGuestSession();
    const paths = spyRequestPaths();
    window.history.pushState({}, "", "/apis");

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "APIs" })).toBeInTheDocument();
    expect(await screen.findByText("API keys are managed by administrators")).toBeInTheDocument();
    expect(screen.getByText("Sign in as an administrator to view and manage API keys.")).toBeInTheDocument();
    await waitFor(() => expect(paths).toContain("/api/swissai/settings"));

    expect(screen.queryByRole("button", { name: "Create API Key" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(restrictedRequests(paths)).toEqual([]);
  });

  it("does not mount or fetch API key, upstream-proxy, or sticky-session surfaces on /settings", async () => {
    useGuestSession();
    const paths = spyRequestPaths();
    window.history.pushState({}, "", "/settings?advanced=1");

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(
      await screen.findByText(
        "You are viewing the dashboard with read-only guest access. Admin controls are disabled.",
      ),
    ).toBeInTheDocument();
    await waitFor(() => expect(paths).toContain("/api/firewall/ips"));
    await waitFor(() => expect(paths).toContain("/api/swissai/settings"));

    expect(screen.queryByRole("button", { name: "Create key" })).not.toBeInTheDocument();
    expect(screen.queryByText("API Keys")).not.toBeInTheDocument();
    expect(screen.queryByText("Sticky sessions")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(restrictedRequests(paths)).toEqual([]);
  });

  it("renders redacted SwissAI keys without mutation or subscription controls for guests", async () => {
    useGuestSession();
    const paths = spyRequestPaths();
    window.history.pushState({}, "", "/accounts");

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "SwissAI Keys" })).toBeInTheDocument();
    expect(await screen.findByText("Shared teaching key")).toBeInTheDocument();
    expect(screen.getByText("sk-rc-…demo")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Need help?" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add key" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Probe|Pause|Edit|Delete/ })).not.toBeInTheDocument();
    expect(restrictedRequests(paths)).toEqual([]);
  });

  it("drops a URL-carried API-key filter and hides its control on /dashboard", async () => {
    useGuestSession();
    const urls = spyRequestUrls();
    window.history.pushState({}, "", "/dashboard?apiKeyId=key_1&status=success");

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "Request Logs" })).toBeInTheDocument();
    await waitFor(() => {
      const logUrls = requestLogUrls(urls);
      expect(logUrls.some((url) => url.pathname === "/api/request-logs")).toBe(true);
      expect(logUrls.some((url) => url.pathname === "/api/request-logs/options")).toBe(true);
    });
    expect(await screen.findByRole("button", { name: "SwissAI keys" })).toBeInTheDocument();

    // No log or facet request carries the hidden filter; other filters survive.
    for (const url of requestLogUrls(urls)) {
      expect(url.searchParams.getAll("apiKeyId")).toEqual([]);
    }
    expect(requestLogUrls(urls).some((url) => url.searchParams.getAll("status").includes("success"))).toBe(true);
    expect(screen.queryByRole("button", { name: "API Keys" })).not.toBeInTheDocument();
    // The stale parameter is removed from the address so it cannot be re-applied.
    await waitFor(() => expect(new URL(window.location.href).searchParams.has("apiKeyId")).toBe(false));
    expect(new URL(window.location.href).searchParams.getAll("status")).toEqual(["success"]);
  });

  it("honours a URL-carried API-key filter and shows its control for writers (regression)", async () => {
    const urls = spyRequestUrls();
    window.history.pushState({}, "", "/dashboard?apiKeyId=key_1");

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "Request Logs" })).toBeInTheDocument();
    await waitFor(() => {
      const logUrls = requestLogUrls(urls);
      expect(logUrls.some((url) => url.pathname === "/api/request-logs")).toBe(true);
      expect(logUrls.some((url) => url.pathname === "/api/request-logs/options")).toBe(true);
    });

    for (const url of requestLogUrls(urls)) {
      expect(url.searchParams.getAll("apiKeyId")).toEqual(["key_1"]);
    }
    // With one key selected the filter control is labelled by that key.
    expect(await screen.findByRole("button", { name: "Default key · sk-test" })).toBeInTheDocument();
    expect(new URL(window.location.href).searchParams.getAll("apiKeyId")).toEqual(["key_1"]);
  });

  it("fetches client-key and SwissAI settings, but not removed provider surfaces, for writers", async () => {
    const paths = spyRequestPaths();
    window.history.pushState({}, "", "/settings?advanced=1");

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    await waitFor(() => expect(paths).toContain("/api/api-keys/"));
    await waitFor(() => expect(paths).toContain("/api/swissai/settings"));
    expect(paths).not.toContain("/api/settings/upstream-proxy");
    expect(paths).not.toContain("/api/sticky-sessions");
    expect(await screen.findByRole("button", { name: "Create key" })).toBeInTheDocument();
  });

  it("keeps the API key page for writers (regression)", async () => {
    const paths = spyRequestPaths();
    window.history.pushState({}, "", "/apis");

    renderWithProviders(<App />);

    expect(await screen.findByRole("button", { name: "Create API Key" })).toBeInTheDocument();
    await waitFor(() => expect(paths).toContain("/api/api-keys/"));
    expect(screen.queryByText("API keys are managed by administrators")).not.toBeInTheDocument();
  });

  it("offers SwissAI key creation without fetching OAuth or proxy topology for writers", async () => {
    const user = userEvent.setup();
    const paths = spyRequestPaths();
    window.history.pushState({}, "", "/accounts");

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "SwissAI Keys" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Add key" }));
    expect(await screen.findByRole("dialog", { name: "Add SwissAI key" })).toBeInTheDocument();
    expect(paths).not.toContain("/api/settings/upstream-proxy");
    expect(paths).not.toContain("/api/settings/runtime/connect-address");
    expect(screen.queryByText("Windows OAuth Help")).not.toBeInTheDocument();
  });

  it("does not render upstream-proxy data cached by an earlier admin session for guests", async () => {
    useGuestSession();
    const paths = spyRequestPaths();
    const cached = createUpstreamProxyAdmin();

    window.history.pushState({}, "", "/settings?advanced=1");
    const settingsRender = renderWithProviders(<App />);
    // Simulates an admin's response still sitting in the cache after the
    // session was downgraded; the disabled guest query still exposes it.
    settingsRender.queryClient.setQueryData(["settings", "upstream-proxy"], cached);

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    await waitFor(() => expect(paths).toContain("/api/firewall/ips"));
    expect(screen.queryByText("Upstream proxy routing")).not.toBeInTheDocument();
    expect(screen.queryByText("Primary proxy")).not.toBeInTheDocument();
    expect(screen.queryByText("Primary pool")).not.toBeInTheDocument();
    settingsRender.unmount();

    window.history.pushState({}, "", "/accounts");
    const accountsRender = renderWithProviders(<App />);
    accountsRender.queryClient.setQueryData(["settings", "upstream-proxy"], cached);

    expect(await screen.findByText("Shared teaching key")).toBeInTheDocument();
    await waitFor(() => expect(paths).toContain("/api/swissai-keys"));
    expect(screen.queryByText("Proxy binding")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Account proxy pool" })).not.toBeInTheDocument();
    expect(screen.queryByText("Primary pool")).not.toBeInTheDocument();
    expect(restrictedRequests(paths)).toEqual([]);
  });
});
