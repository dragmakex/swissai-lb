import { Settings } from "lucide-react";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { getErrorMessageOrNull } from "@/utils/errors";
import { AlertMessage } from "@/components/alert-message";
import { ApiKeysSection } from "@/features/api-keys/components/api-keys-section";
import { useAuthStore, usePermission } from "@/features/auth/hooks/use-auth";
import { FirewallSection } from "@/features/firewall/components/firewall-section";
import { AccessCard } from "@/features/settings/components/access/access-card";
import { AppearanceSettings } from "@/features/settings/components/appearance-settings";
import { DataRetentionSettings } from "@/features/settings/components/data-retention-settings";
import { UpstreamTimeoutSettings } from "@/features/settings/components/upstream-timeout-settings";
import { useSettings } from "@/features/settings/hooks/use-settings";
import { buildSettingsUpdateRequest } from "@/features/settings/payload";
import { SettingsSkeleton } from "@/features/settings/components/settings-skeleton";
import { SwissAIRoutingSettings } from "@/features/swissai/routing-settings";
import { TelemetrySettings } from "@/features/settings/components/telemetry-settings";

export function SettingsPage() {
  const { settingsQuery, updateSettingsMutation } = useSettings();
  const canWrite = useAuthStore(state => state.canWrite);
  const canWriteSecurity = usePermission("security:write");
  const canConfigure = usePermission("ops:write");
  const canReadKeys = usePermission("api_keys:read");
  const canWriteKeys = usePermission("api_keys:write");
  const canReadPool = usePermission("accounts:read");
  const canWritePool = usePermission("accounts:write");
  const personalSignIn = useAuthStore(state => state.passwordManagementEnabled && (state.passwordSessionActive || state.user !== null));
  const settings = settingsQuery.data;
  const { hash } = useLocation();
  useEffect(() => {
    if (settings && hash === "#firewall") document.getElementById("firewall")?.scrollIntoView?.({ block: "start" });
  }, [settings, hash]);
  const error = getErrorMessageOrNull(settingsQuery.error) ?? getErrorMessageOrNull(updateSettingsMutation.error)
    ?? (settingsQuery.error ? "Failed to load settings" : null);
  const busy = updateSettingsMutation.isPending;
  const save = async (payload: Parameters<typeof updateSettingsMutation.mutateAsync>[0]) => { await updateSettingsMutation.mutateAsync(payload); };
  return <div className="animate-fade-in-up space-y-6">
    <div><h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Settings className="size-5 text-primary" />Settings</h1>
      <p className="mt-1 text-sm text-muted-foreground">SwissAI routing, client access, dashboard security and retention.</p></div>
    {!canWrite ? <p className="text-sm text-muted-foreground">You are viewing the dashboard with read-only guest access. Admin controls are disabled.</p> : null}
    {error ? <div role="alert" className="space-y-2"><AlertMessage variant="error">{error}</AlertMessage>
      {settingsQuery.error ? <Button variant="outline" disabled={settingsQuery.isFetching} onClick={() => void settingsQuery.refetch()}>Retry</Button> : null}
    </div> : null}
    {!settings ? (error ? null : <SettingsSkeleton />) : <div className="space-y-4">
      <AppearanceSettings />
      {canConfigure ? <TelemetrySettings disabled={busy} /> : null}
      {canWrite || personalSignIn ? <AccessCard settings={settings} busy={busy} onSave={save} onRefresh={() => settingsQuery.refetch()} /> : null}
      {canReadKeys ? <ApiKeysSection apiKeyAuthEnabled={settings.apiKeyAuthEnabled} hideUpstreamQuotaFromApiKeys={settings.hideUpstreamQuotaFromApiKeys}
        disabled={busy || !canWriteKeys} policyControlsDisabled={busy || !canWriteSecurity}
        onApiKeyAuthEnabledChange={enabled => void save(buildSettingsUpdateRequest(settings, { apiKeyAuthEnabled: enabled }))}
        onHideUpstreamQuotaFromApiKeysChange={enabled => void save(buildSettingsUpdateRequest(settings, { hideUpstreamQuotaFromApiKeys: enabled }))} /> : null}
      {canReadPool ? <SwissAIRoutingSettings disabled={busy || !canWritePool} /> : null}
      <UpstreamTimeoutSettings settings={settings} busy={busy || !canConfigure} onSave={save} />
      <section id="firewall"><FirewallSection disabled={busy || !canWriteSecurity} /></section>
      <DataRetentionSettings settings={settings} busy={busy || !canConfigure} onSave={save} />
    </div>}
  </div>;
}
