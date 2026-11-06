import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { AppearanceSettings } from "@/features/settings/components/appearance-settings";
import i18n from "@/i18n";
import { useThemeStore } from "@/hooks/use-theme";
import { useTimeFormatStore } from "@/hooks/use-time-format";
import { useDateDisplayFormatStore } from "@/hooks/use-date-format";
import { useDashboardPreferencesStore } from "@/hooks/use-dashboard-preferences";

function installLocalStorageMock() {
  const storage = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => {
        storage.set(key, value);
      },
      removeItem: (key: string) => {
        storage.delete(key);
      },
      clear: () => {
        storage.clear();
      },
    },
  });
}

describe("AppearanceSettings", () => {
  beforeEach(() => {
    installLocalStorageMock();
    useThemeStore.setState({ preference: "light", theme: "light", initialized: true });
    useTimeFormatStore.setState({ timeFormat: "12h" });
    useDateDisplayFormatStore.setState({ dateDisplayFormat: "default" });
    useDashboardPreferencesStore.setState({ refreshSeconds: 15 });
  });

  it("updates the dashboard refresh cadence", async () => {
    const user = userEvent.setup();
    render(<AppearanceSettings />);

    const fiveSeconds = screen.getByRole("button", { name: "5s" });
    const fifteenSeconds = screen.getByRole("button", { name: "15s" });
    expect(fifteenSeconds).toHaveAttribute("aria-pressed", "true");

    await user.click(fiveSeconds);

    expect(fiveSeconds).toHaveAttribute("aria-pressed", "true");
    expect(useDashboardPreferencesStore.getState().refreshSeconds).toBe(5);
  });

  it("exposes selected state for the time-format toggle", async () => {
    const user = userEvent.setup();

    render(<AppearanceSettings />);

    const button12h = screen.getByRole("button", { name: /12h/i });
    const button24h = screen.getByRole("button", { name: /24h/i });

    expect(button12h).toHaveAttribute("aria-pressed", "true");
    expect(button24h).toHaveAttribute("aria-pressed", "false");

    await user.click(button24h);

    expect(button12h).toHaveAttribute("aria-pressed", "false");
    expect(button24h).toHaveAttribute("aria-pressed", "true");
    expect(useTimeFormatStore.getState().timeFormat).toBe("24h");
  });

  it("exposes selected state for the date-format toggle", async () => {
    const user = userEvent.setup();

    render(<AppearanceSettings />);

    const buttonDefault = screen.getByRole("button", { name: /default/i });
    const buttonIso = screen.getByRole("button", { name: /iso 8601/i });

    expect(buttonDefault).toHaveAttribute("aria-pressed", "true");
    expect(buttonIso).toHaveAttribute("aria-pressed", "false");

    await user.click(buttonIso);

    expect(buttonDefault).toHaveAttribute("aria-pressed", "false");
    expect(buttonIso).toHaveAttribute("aria-pressed", "true");
    expect(useDateDisplayFormatStore.getState().dateDisplayFormat).toBe("iso8601");
  });

  it.each(["en", "zh-CN"])("omits subscription-only controls in %s", async language => {
    await i18n.changeLanguage(language);
    try {
      render(<AppearanceSettings />);
      expect(screen.queryByRole("switch")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "5H" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "W" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Both" })).not.toBeInTheDocument();
    } finally {
      await i18n.changeLanguage("en");
    }
  });
});
