import { useState } from "react";

import { AlertMessage } from "@/components/alert-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InheritBadge } from "@/features/settings/components/inherit-badge";
import type { DashboardSettings, SettingsUpdateRequest } from "@/features/settings/schemas";

export type DataRetentionSettingsProps = {
  settings: DashboardSettings;
  busy: boolean;
  onSave: (payload: SettingsUpdateRequest) => Promise<void>;
};

export function DataRetentionSettings({ settings, busy, onSave }: DataRetentionSettingsProps) {
  const [days, setDays] = useState(settings.requestLogRetentionOverrideDays?.toString() ?? "");
  const [error, setError] = useState<string | null>(null);
  const value = days === "" ? null : Number(days);
  const valid = value === null || (Number.isInteger(value) && (value === 0 || (value >= 30 && value <= 3650)));

  async function save(payload: SettingsUpdateRequest) {
    setError(null);
    try {
      await onSave(payload);
      if (payload.requestLogRetentionOverrideDays === null) setDays("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save retention");
    }
  }

  return <section className="space-y-4 rounded-xl border bg-card p-5"><h2 className="font-semibold">Metadata retention</h2>
    <form className="space-y-4" onSubmit={event => {
      event.preventDefault();
      if (valid) void save({ expectedVersion: settings.version, requestLogRetentionOverrideDays: value });
    }}>
      <div className="space-y-2"><Label htmlFor="retention-days">Retain request, attempt, audit and continuation metadata (days)</Label>
        <Input id="retention-days" type="number" min={0} max={3650} step={1} value={days}
          placeholder={String(settings.requestLogRetentionDays ?? 0)} disabled={busy} onChange={event => setDays(event.target.value)} />
        <InheritBadge settings={settings} name="request_log_retention_days" field="requestLogRetentionOverrideDays"
          busy={busy} onSave={save} fallbackValue={days === "" ? settings.requestLogRetentionDays ?? 0 : undefined} />
      </div>
      <p className="text-xs text-muted-foreground">0 disables cleanup. Otherwise choose at least 30 days. Prompts, completions and tool arguments are not stored.</p>
      {error ? <AlertMessage variant="error">{error}</AlertMessage> : null}
      <Button type="submit" disabled={busy || !valid}>Save retention</Button>
    </form>
  </section>;
}
