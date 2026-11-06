import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, RefreshCw, Pencil, Trash2, Pause, Play } from "lucide-react";
import { z } from "zod";

import { AlertMessage } from "@/components/alert-message";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { SparklineChart } from "@/components/sparkline-chart";
import { formatDateTimeInline, formatNumber } from "@/utils/formatters";
import { useDateDisplayFormatStore } from "@/hooks/use-date-format";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePermission } from "@/features/auth/hooks/use-auth";
import { del, patch, post } from "@/lib/api-client";
import { SwissAIOverview } from "@/features/swissai/pool-overview";
import { KeySchema, useSwissAIKeys, type SwissAIKey } from "@/features/swissai/hooks";

const PATH = "/api/swissai-keys";

function KeyActivity({ usage, index }: { usage: SwissAIKey["usage"]; index: number }) {
  const trend = useMemo(() => usage?.dailyRequests.map(value => ({ value })) ?? [], [usage]);
  if (!usage) return <span className="text-muted-foreground">Usage unavailable</span>;
  return <div className="min-w-44 space-y-1 text-xs">
    <p>{formatNumber(usage.attempts)} attempted requests · 7 UTC days</p>
    <p>Input {usage.inputTokens == null ? "—" : formatNumber(usage.inputTokens)} · Output {usage.outputTokens == null ? "—" : formatNumber(usage.outputTokens)}</p>
    <p className="text-muted-foreground">{usage.reportedRequests}/{usage.attempts} with reported terminal usage</p>
    <div role="img" aria-label={`Seven-day attempted requests: ${usage.dailyRequests.join(", ")}`}>
      <SparklineChart data={trend} color="var(--primary)" index={index} height={28} />
    </div>
  </div>;
}

export function SwissAIKeysPage() {
  const dateDisplayFormat = useDateDisplayFormatStore(state => state.dateDisplayFormat);
  const query = useSwissAIKeys();
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const client = useQueryClient();
  const canWrite = usePermission("accounts:write");
  const [editing, setEditing] = useState<SwissAIKey | "new" | null>(null);
  const [deleting, setDeleting] = useState<SwissAIKey | null>(null);
  const [name, setName] = useState("");
  const [secret, setSecret] = useState("");
  const [cap, setCap] = useState("4");
  const mutation = useMutation({
    mutationFn: async ({ key, action }: { key: SwissAIKey; action: "pause" | "resume" | "probe" | "delete" }) => {
      if (action === "delete") return del(`${PATH}/${key.id}`);
      return post(`${PATH}/${key.id}/${action}`, z.unknown());
    },
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ["swissai-keys"] }); },
  });
  const save = useMutation({
    mutationFn: () => {
      const body = { name, maxConcurrency: cap ? Number(cap) : null, ...(secret ? { apiKey: secret } : {}) };
      return editing === "new" ? post(PATH, KeySchema, { body }) : patch(`${PATH}/${editing?.id}`, KeySchema, { body });
    },
    onSuccess: async () => {
      setSecret(""); setEditing(null);
      await client.invalidateQueries({ queryKey: ["swissai-keys"] });
      await client.invalidateQueries({ queryKey: ["model-sources"] });
    },
  });
  function edit(key: SwissAIKey | "new") {
    setName(key === "new" ? "" : key.name); setSecret(""); setCap(key === "new" ? "4" : String(key.maxConcurrency ?? ""));
    save.reset(); setEditing(key);
  }
  return <div className="animate-fade-in-up space-y-6">
    <div className="flex items-center justify-between gap-4">
      <div><h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><KeyRound className="size-5 text-primary" />SwissAI Keys</h1>
        <p className="mt-1 text-sm text-muted-foreground">Encrypted upstream credentials. Prompts and completions are not stored.</p></div>
      {canWrite ? <Button onClick={() => edit("new")}><Plus className="mr-2 size-4" />Add key</Button> : null}
    </div>
    <SwissAIOverview />
    {query.error || mutation.error ? <AlertMessage variant="error">{query.error?.message ?? mutation.error?.message}</AlertMessage> : null}
    <div className="overflow-x-auto rounded-xl border bg-card">
      <table className="w-full text-left text-sm"><thead className="border-b text-muted-foreground"><tr>
        <th className="p-4">Label / key</th><th className="p-4">State</th><th className="p-4">In flight / cap</th><th className="p-4">Recent activity</th><th className="p-4">Last outcome</th><th className="p-4">Actions</th>
      </tr></thead><tbody>{query.data?.map((key, index) => <tr key={key.id} className="border-b last:border-0">
        <td className="p-4"><p className="font-medium">{key.name}</p><code className="text-xs text-muted-foreground">{key.keyPrefix}</code></td>
        <td className="p-4"><Badge variant={key.status === "active" ? "default" : "secondary"}>{key.status.replaceAll("_", " ")}</Badge>
          {key.cooldownUntil && key.status === "cooling_down" ? <p className="mt-1 text-xs">{Math.max(0, Math.ceil((new Date(key.cooldownUntil).getTime() - now) / 1000))}s remaining</p> : null}
          {key.failureReason ? <p className="mt-1 text-xs text-muted-foreground">{key.failureReason}</p> : null}</td>
        <td className="p-4">{key.inFlight} / {key.maxConcurrency ?? "default"}</td>
        <td className="p-4"><KeyActivity usage={key.usage} index={index} /></td>
        <td className="p-4 text-xs"><p>Success {key.lastSuccessAt ? formatDateTimeInline(key.lastSuccessAt, dateDisplayFormat) : "—"}</p>
          <p className="mt-1 text-muted-foreground">Failure {key.lastFailureAt ? formatDateTimeInline(key.lastFailureAt, dateDisplayFormat) : "—"}</p></td>
        <td className="p-4">{canWrite ? <div className="flex gap-1">
          <Button variant="ghost" size="icon" aria-label={`Probe ${key.name}`} disabled={mutation.isPending} onClick={() => mutation.mutate({ key, action: "probe" })}><RefreshCw className="size-4" /></Button>
          <Button variant="ghost" size="icon" aria-label={`${key.enabled ? "Pause" : "Resume"} ${key.name}`} disabled={mutation.isPending} onClick={() => mutation.mutate({ key, action: key.enabled ? "pause" : "resume" })}>{key.enabled ? <Pause className="size-4" /> : <Play className="size-4" />}</Button>
          <Button variant="ghost" size="icon" aria-label={`Edit ${key.name}`} onClick={() => edit(key)}><Pencil className="size-4" /></Button>
          <Button variant="ghost" size="icon" aria-label={`Delete ${key.name}`} onClick={() => setDeleting(key)}><Trash2 className="size-4" /></Button>
        </div> : "Read only"}</td>
      </tr>)}</tbody></table>
      {!query.isPending && query.data?.length === 0 ? <p className="p-8 text-center text-muted-foreground">No SwissAI keys yet. Add an operator-authorized sk-rc-… key to start routing.</p> : null}
    </div>
    <Dialog open={editing !== null} onOpenChange={open => { if (!open) { setEditing(null); setSecret(""); } }}>
      <DialogContent><DialogHeader><DialogTitle>{editing === "new" ? "Add SwissAI key" : "Edit SwissAI key"}</DialogTitle></DialogHeader>
        <form className="space-y-4" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
          <div className="space-y-2"><Label htmlFor="swissai-name">Label</Label><Input id="swissai-name" value={name} onChange={e => setName(e.target.value)} required maxLength={128} /></div>
          <div className="space-y-2"><Label htmlFor="swissai-secret">{editing === "new" ? "SwissAI key" : "Replacement key (leave blank to keep)"}</Label><Input id="swissai-secret" type="password" autoComplete="new-password" value={secret} onChange={e => setSecret(e.target.value)} required={editing === "new"} placeholder="sk-rc-…" /></div>
          <div className="space-y-2"><Label htmlFor="swissai-cap">Maximum concurrent requests</Label><Input id="swissai-cap" type="number" min={1} max={1000} value={cap} onChange={e => setCap(e.target.value)} /></div>
          {save.error ? <AlertMessage variant="error">{save.error.message}</AlertMessage> : null}
          <Button type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save key"}</Button>
        </form>
      </DialogContent>
    </Dialog>
    <ConfirmDialog open={deleting !== null} title="Delete SwissAI key?" description="New requests stop immediately. An active key must drain before its secret is removed." confirmLabel="Delete" onOpenChange={open => { if (!open) setDeleting(null); }} onConfirm={() => { if (deleting) mutation.mutate({ key: deleting, action: "delete" }, { onSuccess: () => setDeleting(null) }); }} />
  </div>;
}
