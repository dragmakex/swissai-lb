import { describe, expect, it, vi } from "vitest";

import { downloadRequestLogs } from "@/features/swissai/request-log-export";
import { createRequestLogEntry } from "@/test/mocks/factories";
import { downloadCsv } from "@/utils/csv";

vi.mock("@/utils/csv", () => ({ downloadCsv: vi.fn() }));

describe("Request-log CSV", () => {
  it("exports only allowlisted metadata and preserves unknown versus observed zero usage", () => {
    const row = {
      ...createRequestLogEntry({ route: "/v1/responses", stream: false, inputTokens: 0, outputTokensRaw: null }),
      prompt: "private prompt", completion: "private completion", apiKey: "private credential",
    };
    downloadRequestLogs([row]);
    const [name, rows] = vi.mocked(downloadCsv).mock.calls[0];
    expect(name).toBe("swissai-requests.csv");
    expect(rows).toHaveLength(2);
    const [headers, values] = rows;
    expect(values[headers.indexOf("route")]).toBe("/v1/responses");
    expect(values[headers.indexOf("stream")]).toBe(false);
    expect(values[headers.indexOf("input_tokens")]).toBe(0);
    expect(values[headers.indexOf("output_tokens")]).toBeNull();
    expect(JSON.stringify(rows)).not.toMatch(/private prompt|private completion|private credential/);
    expect(headers).not.toContain("cost_usd");
  });
});
