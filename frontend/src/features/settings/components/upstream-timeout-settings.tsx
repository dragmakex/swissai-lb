import { useState } from "react";

import { AlertMessage } from "@/components/alert-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InheritBadge } from "@/features/settings/components/inherit-badge";
import type { DashboardSettings, SettingsUpdateRequest } from "@/features/settings/schemas";

export type UpstreamTimeoutSettingsProps = {
  settings: DashboardSettings;
  busy: boolean;
  onSave: (payload: SettingsUpdateRequest) => Promise<void>;
};
const FIELDS = [
  ["upstreamConnectTimeoutSeconds", "upstream_connect_timeout_seconds", "Connection timeout"],
  ["proxyRequestBudgetSeconds", "proxy_request_budget_seconds", "Whole non-stream request budget"],
  ["httpResponsesStreamRequestBudgetSeconds", "http_responses_stream_request_budget_seconds", "Whole streaming request budget"],
  ["streamIdleTimeoutSeconds", "stream_idle_timeout_seconds", "Stream idle timeout"],
] as const;
type Field = (typeof FIELDS)[number][0];

export function UpstreamTimeoutSettings({ settings, busy, onSave }: UpstreamTimeoutSettingsProps) {
  const [initial] = useState<Record<Field, string>>(() => Object.fromEntries(FIELDS.map(([field, name]) => [
    field, settings.provenance?.[name]?.source === "dashboard" ? String(settings[field]) : "",
  ])) as Record<Field, string>);
  const [draft, setDraft] = useState(initial);
  const changed = FIELDS.filter(([field]) => draft[field] !== initial[field]);
  const [error, setError] = useState<string | null>(null);
  const effective = (field: Field) => draft[field] === "" ? settings[field] : Number(draft[field]);
  const valid = FIELDS.every(([field]) => Number.isFinite(effective(field)) && effective(field) > 0 && effective(field) <= 86400)
    && effective("upstreamConnectTimeoutSeconds") <= Math.min(effective("proxyRequestBudgetSeconds"), effective("httpResponsesStreamRequestBudgetSeconds"));

  async function save(payload: SettingsUpdateRequest) {
    setError(null);
    try {
      await onSave(payload);
      for (const [field] of FIELDS) if (payload[field] === null) setDraft(previous => ({ ...previous, [field]: "" }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save timeouts");
    }
  }

  return <section className="space-y-4 rounded-xl border bg-card p-5"><h2 className="font-semibold">Upstream timeouts</h2>
    <form className="space-y-4" onSubmit={event => {
      event.preventDefault();
      if (!valid) return;
      const payload: SettingsUpdateRequest = { expectedVersion: settings.version };
      for (const [field] of changed) payload[field] = draft[field] === "" ? null : Number(draft[field]);
      void save(payload);
    }}>
      {FIELDS.map(([field, name, label]) => <div key={field} className="space-y-2"><Label htmlFor={field}>{label} (seconds)</Label>
        <Input id={field} type="number" step="any" min={0.1} max={86400}
          value={draft[field]} placeholder={String(settings[field])} disabled={busy}
          onChange={event => setDraft({ ...draft, [field]: event.target.value })} />
        <InheritBadge settings={settings} name={name} field={field} busy={busy} onSave={save}
          fallbackValue={draft[field] === "" ? settings[field] : undefined} />
      </div>)}
      <p className="text-xs text-muted-foreground">Every attempt shares the original deadline. Retries do not reset the clock.</p>
      {!valid ? <p role="alert" className="text-sm text-destructive">Timeouts must be positive and at most 86400 seconds. Connection timeout must fit both request budgets.</p> : null}
      {error ? <AlertMessage variant="error">{error}</AlertMessage> : null}
      <Button type="submit" disabled={busy || !valid || changed.length === 0}>Save timeouts</Button>
    </form>
  </section>;
}
