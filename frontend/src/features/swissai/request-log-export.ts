import type { RequestLog } from "@/features/dashboard/schemas";
import { downloadCsv } from "@/utils/csv";

export function downloadRequestLogs(requests: RequestLog[]): void {
  downloadCsv("swissai-requests.csv", [
    ["requested_at", "request_id", "route", "model", "stream", "client_key", "upstream_key_id", "upstream_key_label",
      "status", "upstream_status_code", "attempts", "failover_reason", "input_tokens", "output_tokens",
      "cached_input_tokens", "reasoning_tokens", "first_token_ms", "latency_ms", "error_code"],
    ...requests.map(r => [r.requestedAt, r.requestId, r.route, r.model, r.stream, r.apiKeyName, r.modelSourceId,
      r.upstreamKeyLabel, r.status, r.upstreamStatusCode, r.attemptCount, r.failoverReason, r.inputTokens,
      r.outputTokensRaw, r.cachedInputTokens, r.reasoningTokens, r.latencyFirstTokenMs, r.latencyMs, r.errorCode]),
  ]);
}
