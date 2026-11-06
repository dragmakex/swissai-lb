import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertMessage } from "@/components/alert-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { put } from "@/lib/api-client";
import { PoolSettingsSchema as Schema, useSwissAIKeys, useSwissAIPoolSettings, type PoolSettings as Settings } from "@/features/swissai/hooks";
const labels = { least_inflight: "Least in-flight (recommended)", round_robin: "Round robin", fill_first: "Fill first", single_key: "Single key (debugging)" };

export function SwissAIRoutingSettings({ disabled }: { disabled: boolean }) {
  const query = useSwissAIPoolSettings();
  if (!query.data) return query.error ? <AlertMessage variant="error">{query.error.message}</AlertMessage> : <p>Loading routing settings…</p>;
  return <RoutingForm key={JSON.stringify(query.data)} initial={query.data} disabled={disabled} />;
}

function RoutingForm({ initial, disabled }: { initial: Settings; disabled: boolean }) {
  const [draft, setDraft] = useState(initial);
  const client = useQueryClient();
  const keys = useSwissAIKeys();
  const mutation = useMutation({ mutationFn: () => put("/api/swissai/settings", Schema, { body: draft }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["swissai-settings"] }) });
  const busy = disabled || mutation.isPending;
  return <section className="space-y-4 rounded-xl border bg-card p-5"><h2 className="font-semibold">SwissAI routing</h2>
    <form className="space-y-4" onSubmit={e => { e.preventDefault(); mutation.mutate(); }}>
      <div className="space-y-2"><Label>Selection strategy</Label><Select value={draft.strategy} disabled={busy} onValueChange={value => setDraft({ ...draft, strategy: Schema.shape.strategy.parse(value) })}>
        <SelectTrigger aria-label="Selection strategy"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(labels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>
      {draft.strategy === "single_key" ? <div className="space-y-2"><Label>Single key</Label><Select value={draft.single_key_id ?? ""} disabled={busy} onValueChange={value => setDraft({ ...draft, single_key_id: value })}>
        <SelectTrigger aria-label="Single key"><SelectValue placeholder="Choose a SwissAI key" /></SelectTrigger><SelectContent>{keys.data?.map(key => <SelectItem key={key.id} value={key.id}>{key.name}</SelectItem>)}</SelectContent></Select></div> : null}
      {([ ["default_max_concurrency", "Default maximum concurrency per key", 1, 1000], ["first_byte_timeout_seconds", "First-byte timeout (seconds)", 0.05, 600], ["admission_timeout_seconds", "Admission timeout (seconds)", 0, 300], ["max_queue_size", "Maximum queued requests", 0, 10000] ] as const).map(([field, label, min, max]) => <div className="space-y-2" key={field}>
        <Label htmlFor={field}>{label}</Label><Input id={field} type="number" step="any" min={min} max={max} disabled={busy} value={draft[field]} onChange={e => setDraft({ ...draft, [field]: Number(e.target.value) })} required />
      </div>)}
      <p className="text-sm text-muted-foreground">Up to three distinct keys are tried before output starts. A pre-output timeout may consume SwissAI usage twice. Streaming output is never combined across keys.</p>
      {mutation.error ? <AlertMessage variant="error">{mutation.error.message}</AlertMessage> : null}
      <Button disabled={busy} type="submit">Save routing</Button>
    </form>
  </section>;
}
