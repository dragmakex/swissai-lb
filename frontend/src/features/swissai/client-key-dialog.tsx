import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { AlertMessage } from "@/components/alert-message";
import { ModelMultiSelect } from "@/features/api-keys/components/model-multi-select";
import { ModelSourceMultiSelect } from "@/features/model-sources/components/model-source-multi-select";
import { ExpiryPicker } from "@/features/api-keys/components/expiry-picker";
import { LimitRuleCard } from "@/features/api-keys/components/limit-rule-card";
import { LimitUsageBars } from "@/features/api-keys/components/limit-usage-bars";
import type { ApiKey, ApiKeyCreateRequest, ApiKeyUpdateRequest, LimitRuleCreate } from "@/features/api-keys/schemas";

type Props = { open: boolean; busy: boolean; onOpenChange: (open: boolean) => void };
export type ApiKeyCreateDialogProps = Props & { onSubmit: (payload: ApiKeyCreateRequest) => Promise<void> };
export type ApiKeyEditDialogProps = Props & { apiKey?: ApiKey | null; onSubmit: (payload: ApiKeyUpdateRequest) => Promise<void> };

export function ApiKeyCreateDialog(props: ApiKeyCreateDialogProps) {
  return <Dialog open={props.open} onOpenChange={props.onOpenChange}><DialogContent className="max-h-[90vh] overflow-y-auto"><DialogHeader>
    <DialogTitle>Create client key</DialogTitle><DialogDescription>The local client key is shown once. It is not a SwissAI upstream key.</DialogDescription>
  </DialogHeader>{props.open ? <ClientKeyForm busy={props.busy} onSubmit={props.onSubmit} onDone={() => props.onOpenChange(false)} /> : null}</DialogContent></Dialog>;
}
export function ApiKeyEditDialog(props: ApiKeyEditDialogProps) {
  return <Dialog open={props.open} onOpenChange={props.onOpenChange}><DialogContent className="max-h-[90vh] overflow-y-auto"><DialogHeader>
    <DialogTitle>Edit client key</DialogTitle><DialogDescription>Set expiry, model access, allowed SwissAI keys and token limits.</DialogDescription>
  </DialogHeader>{props.open && props.apiKey ? <ClientKeyForm key={props.apiKey.id} initial={props.apiKey} busy={props.busy} onSubmit={props.onSubmit} onDone={() => props.onOpenChange(false)} /> : null}</DialogContent></Dialog>;
}

function ClientKeyForm({ initial, busy, onSubmit, onDone }: { initial?: ApiKey; busy: boolean; onSubmit: (payload: ApiKeyCreateRequest) => Promise<void>; onDone: () => void }) {
  const [name, setName] = useState(initial?.name ?? "");
  const [models, setModels] = useState(initial?.allowedModels ?? []);
  const [restrictModels, setRestrictModels] = useState(initial?.allowedModels != null);
  const [keys, setKeys] = useState(initial?.assignedSourceIds ?? []);
  const [restrictKeys, setRestrictKeys] = useState(initial?.sourceAssignmentScopeEnabled ?? false);
  const [expiry, setExpiry] = useState<Date | null>(initial?.expiresAt ? new Date(initial.expiresAt) : null);
  const [rules, setRules] = useState<LimitRuleCreate[]>(initial?.limits.map(({ limitType, limitWindow, maxValue, modelFilter }) => ({ limitType, limitWindow, maxValue, modelFilter })) ?? []);
  const [error, setError] = useState<string | null>(null);
  return <form className="space-y-4" onSubmit={async e => {
    e.preventDefault(); setError(null);
    try { await onSubmit({ name, allowedModels: restrictModels ? models : null, assignedSourceIds: restrictKeys ? keys : null, expiresAt: expiry?.toISOString() ?? null, limits: rules }); onDone(); }
    catch (error) { setError(error instanceof Error ? error.message : "Could not save client key"); }
  }}>
    <div className="space-y-2"><Label htmlFor="client-name">Name</Label><Input id="client-name" value={name} onChange={e => setName(e.target.value)} required maxLength={128} /></div>
    <div className="flex items-center justify-between"><Label htmlFor="restrict-models">Restrict models</Label><Switch id="restrict-models" checked={restrictModels} onCheckedChange={setRestrictModels} /></div>
    {restrictModels ? <><ModelMultiSelect value={models} onChange={setModels} placeholder="No models selected" /><p className="text-xs text-muted-foreground">An empty restricted list allows no models.</p></> : null}
    <div className="flex items-center justify-between"><Label htmlFor="restrict-keys">Restrict allowed SwissAI keys</Label><Switch id="restrict-keys" checked={restrictKeys} onCheckedChange={setRestrictKeys} /></div>
    {restrictKeys ? <><ModelSourceMultiSelect value={keys} onChange={setKeys} placeholder="No upstream keys selected" /><p className="text-xs text-muted-foreground">An empty restricted list allows no upstream keys.</p></> : null}
    <div className="space-y-2"><Label>Expires</Label><ExpiryPicker value={expiry} onChange={setExpiry} /></div>
    <div className="space-y-2"><Label>Token limits</Label>{rules.map((rule, index) => <LimitRuleCard key={index} rule={rule} onChange={next => setRules(rules.map((item, i) => i === index ? next : item))} onRemove={() => setRules(rules.filter((_, i) => i !== index))} />)}
      <Button type="button" variant="outline" onClick={() => setRules([...rules, { limitType: "total_tokens", limitWindow: "weekly", maxValue: 100000, modelFilter: null }])}>Add token limit</Button>
      <p className="text-xs text-muted-foreground">SwissAI pricing is unknown. Cost and subscription-credit limits are not offered.</p>
    </div>
    {initial ? <LimitUsageBars limits={initial.limits} /> : null}
    {error ? <AlertMessage variant="error">{error}</AlertMessage> : null}<Button type="submit" disabled={busy || rules.some(rule => rule.maxValue < 1)}>Save client key</Button>
  </form>;
}
