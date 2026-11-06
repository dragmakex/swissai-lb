import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import type { RequestLog } from "@/features/dashboard/schemas";
import { formatElapsed } from "@/utils/formatters";

function median(values: (number | null | undefined)[]): number | null {
  const known = values.filter((value): value is number => value != null).sort((a, b) => a - b);
  if (!known.length) return null;
  const middle = Math.floor(known.length / 2);
  return known.length % 2 ? known[middle] : (known[middle - 1] + known[middle]) / 2;
}

function percent(count: number, total: number): string {
  return total ? `${(100 * count / total).toFixed(1)}%` : "—";
}

export function RecentRequestHealth({ requests }: { requests: RequestLog[] }) {
  const stats = useMemo(() => {
    const attempts = requests.filter(request => request.attemptCount != null);
    const failures = new Map<string, number>();
    for (const request of requests) {
      if (request.status !== "ok") {
        const reason = request.errorCode ?? (request.status === "cancelled" ? "client_cancelled" : "unknown_error");
        failures.set(reason, (failures.get(reason) ?? 0) + 1);
      }
    }
    return {
      success: percent(requests.filter(request => request.status === "ok").length, requests.length),
      failover: percent(attempts.filter(request => (request.attemptCount ?? 0) > 1).length, attempts.length),
      attemptsObserved: attempts.length,
      firstToken: median(requests.map(request => request.latencyFirstTokenMs)),
      latency: median(requests.map(request => request.latencyMs)),
      failures: Array.from(failures).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])),
    };
  }, [requests]);
  if (!requests.length) return null;
  const measures = [
    ["Success rate", stats.success],
    ["Failover rate", `${stats.failover} (${stats.attemptsObserved} observed)`],
    ["Median first-token latency", formatElapsed(stats.firstToken)],
    ["Median latency", formatElapsed(stats.latency)],
  ];
  return (
    <section className="space-y-3 rounded-xl border bg-card p-4" aria-label="Visible request-log page quality">
      <p className="text-xs text-muted-foreground">
        Current visible log page · {requests.length} requests · includes active filters
      </p>
      <dl className="flex flex-wrap gap-x-8 gap-y-3 text-sm">
        {measures.map(([label, value]) => (
          <div key={label} role="group" aria-label={label}>
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      {stats.failures.length ? (
        <div className="flex flex-wrap items-center gap-2 text-xs" aria-label="Recent failure classifications">
          <span className="text-muted-foreground">Recent failures</span>
          {stats.failures.map(([reason, count]) => (
            <Badge key={reason} variant="secondary">{reason} × {count}</Badge>
          ))}
        </div>
      ) : null}
    </section>
  );
}
