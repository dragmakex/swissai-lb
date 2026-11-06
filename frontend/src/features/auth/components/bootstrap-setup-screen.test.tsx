import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { BootstrapSetupScreen } from "@/features/auth/components/bootstrap-setup-screen";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import i18n from "@/i18n";

afterEach(async () => {
  cleanup();
  await act(async () => { await i18n.changeLanguage("en"); });
});

describe("Fork bootstrap guidance", () => {
  it.each(["en", "ko", "zh-CN"])("identifies the secret file and fork environment in %s", async language => {
    await act(async () => { await i18n.changeLanguage(language); });
    useAuthStore.setState({
      bootstrapRequired: true, bootstrapTokenConfigured: true, passwordRequired: false,
      localPasswordConfigured: false, passwordManagementEnabled: true, authMode: "standard",
    });
    const user = userEvent.setup();
    const { container } = render(<BootstrapSetupScreen />);
    expect(container).toHaveTextContent("SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN");
    expect(container).toHaveTextContent("bootstrap.token");
    expect(container).not.toHaveTextContent("CODEX_LB_");
    expect(container).not.toHaveTextContent(/server logs|서버 로그|服务器日志/);
    await user.click(screen.getByRole("button"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN/)).toHaveTextContent("bootstrap.token");
    expect(dialog).not.toHaveTextContent("CODEX_LB_");
  });
});
