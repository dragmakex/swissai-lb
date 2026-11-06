import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { get } from "@/lib/api-client";
import { usePermission } from "@/features/auth/hooks/use-auth";

const KeyUsageSchema = z.object({
  windowStart: z.string(), windowEnd: z.string(), attempts: z.number(), reportedRequests: z.number(),
  inputTokens: z.number().nullable(), outputTokens: z.number().nullable(), dailyRequests: z.array(z.number()).length(7),
});

export const KeySchema = z.object({
  id: z.string(), name: z.string(), keyPrefix: z.string(), status: z.string(), enabled: z.boolean(),
  cooldownUntil: z.string().nullable(), failureReason: z.string().nullable(), maxConcurrency: z.number().nullable(),
  inFlight: z.number(), lastSuccessAt: z.string().nullable(), lastFailureAt: z.string().nullable(), createdAt: z.string(),
  // Older replicas must not turn missing usage observations into zero.
  usage: KeyUsageSchema.optional(),
});
export type SwissAIKey = z.infer<typeof KeySchema>;

export const PoolSettingsSchema = z.object({
  strategy: z.enum(["least_inflight", "round_robin", "fill_first", "single_key"]), single_key_id: z.string().nullable(),
  default_max_concurrency: z.number(), first_byte_timeout_seconds: z.number(), admission_timeout_seconds: z.number(), max_queue_size: z.number(),
});
export type PoolSettings = z.infer<typeof PoolSettingsSchema>;

export function useSwissAIPoolSettings() {
  const enabled = usePermission("accounts:read");
  return useQuery({ queryKey: ["swissai-settings"], enabled, queryFn: () => get("/api/swissai/settings", PoolSettingsSchema) });
}

export function useSwissAIKeys() {
  const enabled = usePermission("accounts:read");
  return useQuery({ queryKey: ["swissai-keys"], enabled, queryFn: () => get("/api/swissai-keys", z.array(KeySchema)), refetchInterval: 5000 });
}
