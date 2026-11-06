import type { DailyReportRow } from "../schemas";

export type CostPerDayChartProps = { startDate: string; endDate: string; data: DailyReportRow[] };

export function CostPerDayChart({ startDate, endDate }: CostPerDayChartProps) {
  return <section className="rounded-xl border bg-card p-5"><h3 className="font-semibold">SwissAI cost —</h3>
    <p className="mt-2 text-sm text-muted-foreground">{startDate} – {endDate}</p>
    <p className="mt-2 text-sm text-muted-foreground">SwissAI does not publish authoritative per-model pricing. Token usage is reported separately; a zero-cost curve would be misleading.</p>
  </section>;
}
