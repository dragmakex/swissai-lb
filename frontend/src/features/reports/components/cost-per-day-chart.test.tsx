import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DailyReportRow } from "../schemas";
import { CostPerDayChart } from "./cost-per-day-chart";

function row(date: string, costUsd: number): DailyReportRow {
  return { date, costUsd, requests: 1, conversations: 0, inputTokens: 2, outputTokens: 3,
    reasoningTokens: 0, cachedInputTokens: 0, activeAccounts: 1, cancelledCount: 0, errorCount: 0 };
}

describe("SwissAI cost disclosure", () => {
  it.each([
    { name: "reported-looking historical numbers", data: [row("2026-06-05", 3.77)] },
    { name: "large historical dollar amounts", data: [row("2026-06-05", 1400)] },
    { name: "missing selected days", data: [row("2026-06-05", 3.77), row("2026-06-07", 4.54)] },
    { name: "no observations", data: [] },
  ])("does not fabricate a cost curve for $name", ({ data }) => {
    const { container } = render(<CostPerDayChart startDate="2026-06-05" endDate="2026-06-07" data={data} />);
    expect(screen.getByRole("heading", { name: "SwissAI cost —" })).toBeInTheDocument();
    expect(screen.getByText("2026-06-05 – 2026-06-07")).toBeInTheDocument();
    expect(screen.getByText(/does not publish authoritative per-model pricing/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\$0|\$3\.77|\$1,?400|\$4\.54/);
    expect(container.querySelector("svg")).toBeNull();
  });
});
