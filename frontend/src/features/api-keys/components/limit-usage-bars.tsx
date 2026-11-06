import { useTranslation } from "react-i18next";

import type { ApiKey } from "@/features/api-keys/schemas";
import { formatCompactNumber } from "@/utils/formatters";

export function LimitUsageBars({ limits }: { limits: ApiKey["limits"] }) {
  const { t } = useTranslation();
  const tokenLimits = limits.filter(limit => limit.limitType.endsWith("tokens"));
  if (!tokenLimits.length) return null;
  return (
    <section className="space-y-2">
      <h4 className="text-xs font-medium text-muted-foreground">{t("apiKeys.form.currentUsage")}</h4>
      {tokenLimits.map(limit => {
        const percent = limit.maxValue > 0 ? Math.max(0, Math.min(100, 100 * limit.currentValue / limit.maxValue)) : 0;
        const label = `${t(`apiKeys.limitTypes.${limit.limitType}`)} (${limit.limitWindow}, ${limit.modelFilter ?? "all"})`;
        return <div className="rounded border p-2" key={limit.id}>
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="text-muted-foreground">{label}</span>
            <span>{formatCompactNumber(limit.currentValue)} / {formatCompactNumber(limit.maxValue)}</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar"
            aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
            <div className={percent >= 90 ? "h-full bg-destructive" : "h-full bg-primary"} style={{ width: `${percent}%` }} />
          </div>
        </div>;
      })}
    </section>
  );
}
