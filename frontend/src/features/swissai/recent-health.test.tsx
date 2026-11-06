import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createRequestLogEntry } from "@/test/mocks/factories";
import { RecentRequestHealth } from "@/features/swissai/recent-health";


describe("Visible request health", () => {
  it("labels its sample and reports rates, medians and failure classifications", () => {
    render(<RecentRequestHealth requests={[
      createRequestLogEntry({ requestId: "a", status: "ok", attemptCount: 2, latencyMs: 100, latencyFirstTokenMs: 0 }),
      createRequestLogEntry({ requestId: "b", status: "error", errorCode: "pre_output_timeout", attemptCount: 1, latencyMs: 300, latencyFirstTokenMs: null }),
    ]} />);
    expect(screen.getByText("Current visible log page · 2 requests · includes active filters")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "Success rate" })).getByText("50.0%")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Failover rate" })).toHaveTextContent("50.0% (2 observed)");
    expect(screen.getByRole("group", { name: "Median latency" })).toHaveTextContent("200");
    expect(screen.getByRole("group", { name: "Median first-token latency" })).toHaveTextContent("0");
    expect(screen.getByRole("group", { name: "Median first-token latency" })).not.toHaveTextContent("—");
    expect(screen.getByText("pre_output_timeout × 1")).toBeInTheDocument();
  });

  it("does not turn absent observations into zero rates or timings", () => {
    render(<RecentRequestHealth requests={[
      createRequestLogEntry({ attemptCount: undefined, latencyMs: null, latencyFirstTokenMs: null }),
    ]} />);
    expect(screen.getByRole("group", { name: "Failover rate" })).toHaveTextContent("— (0 observed)");
    expect(screen.getByRole("group", { name: "Median first-token latency" })).not.toHaveTextContent("0 ms");
    expect(screen.queryByLabelText("Recent failure classifications")).not.toBeInTheDocument();
  });

  it("does not present an empty sample as health evidence", () => {
    render(<RecentRequestHealth requests={[]} />);
    expect(screen.queryByLabelText("Visible request-log page quality")).not.toBeInTheDocument();
  });
});
