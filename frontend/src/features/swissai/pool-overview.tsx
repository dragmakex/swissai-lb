import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { AlertMessage } from "@/components/alert-message";
import { usePermission } from "@/features/auth/hooks/use-auth";
import { useSwissAIKeys } from "@/features/swissai/hooks";
import { get } from "@/lib/api-client";

export function SwissAIOverview() {
  const canRead = usePermission("accounts:read");
  const keys = useSwissAIKeys();
  const catalog = useQuery({
    queryKey: ["swissai-catalog"], enabled: canRead, queryFn: () => get("/api/swissai/catalog", z.object({
      models: z.array(z.object({ id: z.string() }).passthrough()), ageSeconds: z.number().nullable(), lastError: z.string().nullable(),
    })), refetchInterval: 30000,
  });
  if (!canRead) return <p className="text-sm text-muted-foreground">Pool details require SwissAI key read permission.</p>;
  const states = ["active", "cooling_down", "paused", "invalid"];
  return <section className="space-y-4" aria-label="SwissAI pool health">
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{states.map(state => <div className="rounded-xl border bg-card p-5" key={state}>
      <p className="text-sm text-muted-foreground">{state.replaceAll("_", " ")}</p>
      <p className="mt-2 text-3xl font-semibold">{keys.data?.filter(key => key.status === state).length ?? "—"}</p>
    </div>)}</div>
    <div className="rounded-xl border bg-card p-4 text-sm">
      <span className="font-medium">Live model catalog</span>{" · "}{catalog.data?.models.length ?? "—"} models{" · "}
      {catalog.data?.ageSeconds == null ? "Not loaded" : `Updated ${Math.round(catalog.data.ageSeconds)}s ago`}
      {catalog.data?.lastError ? <p className="mt-2 text-destructive">{catalog.data.lastError}</p> : null}
    </div>
    {keys.error ? <AlertMessage variant="error">{keys.error.message}</AlertMessage> : null}
  </section>;
}
