# Historical SwissAI product brief

> Preserved initial planning input, not the current operator contract. Normative behavior lives in [SwissAI requirements](../../specs/swissai-key-pool/spec.md) and active change deltas. Deployment scope and profile-based key probing below were superseded by the single-node, inference-probe and delivery-cleanup changes. This record is retained for provenance, not as a second source of truth.

**Status:** Draft for implementation\
**Target repository:** `swissai-lb`\
**Upstream baseline:** [`Soju06/codex-lb`](https://github.com/Soju06/codex-lb) commit `72630bbfeee9e3b0d9acfb95e2b1e706b8b0188e` (`1.25.0-beta.9`)\
**Primary upstream API:** `https://api.swissai.svc.cscs.ch/v1`\
**Risk tier:** T2 — encrypted credentials, request routing, concurrency, and retry state

## 1. Summary

`swissai-lb` is a self-hosted OpenAI-compatible proxy and dashboard for pooling multiple operator-authorized SwissAI API keys. Clients use one stable local endpoint and, optionally, one local client API key. The proxy chooses an eligible SwissAI key for each request, tracks observed usage and health, and transparently tries another eligible key when a request fails before a response is committed to the client.

The project is a maintained fork of `codex-lb`. It preserves the upstream project's applicable user experience and operational qualities—single-command deployment, dashboard authentication, encrypted secrets, client API keys, request logs, usage reporting, routing controls, SQLite/PostgreSQL support, health checks, metrics, and Docker/Kubernetes packaging—while replacing ChatGPT account/OAuth routing with SwissAI bearer-key routing.

### One-sentence promise

> Point an OpenAI-compatible client at one local URL and safely spread requests across several authorized SwissAI API keys, automatically failing over before output begins when a key is throttled or an upstream attempt fails.

## 2. Meaning of “one-to-one codex-lb”

“One-to-one” means the fork starts from the pinned `codex-lb` source and retains provider-independent behavior, layout, deployment modes, security controls, and quality gates wherever SwissAI can support the same contract.

It does **not** mean fabricating support for ChatGPT-only APIs. The following upstream `codex-lb` capabilities have no confirmed SwissAI equivalent and must be removed, hidden, or return an explicit unsupported error rather than silently misbehave:

- ChatGPT OAuth login, token refresh, `auth.json` import/export, workspace seats, and account reauthentication.
- ChatGPT 5-hour/weekly/monthly quota windows and rate-limit reset credits.
- `/responses/compact` and ChatGPT server-side compaction.
- ChatGPT files, images, realtime/live voice, Codex control, analytics, safety, memories, and web-search routes.
- ChatGPT upstream WebSocket transport and its bridge/session-ring behavior.
- OpenAI subscription plan, pricing, and account-capacity assumptions.

The retained UI should reuse the upstream component system and page structure. Provider-specific labels and controls must be changed; dead OpenAI controls must not remain as nonfunctional decoration.

## 3. Source facts and assumptions

### 3.1 Confirmed SwissAI contract

The SwissAI guide documents:

- Bearer-key authentication using keys shaped like `sk-rc-...`.
- Base URL `https://api.swissai.svc.cscs.ch/v1`.
- `GET /v1/models` for live model discovery.
- `POST /v1/chat/completions` with OpenAI-compatible request and response shapes.
- Streaming through the OpenAI-compatible API.

The live public OpenAPI document at `https://api.swissai.svc.cscs.ch/openapi.json`, inspected while drafting this specification, also lists:

- `POST /v1/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`
- `GET /v1/models_detailed`
- Authenticated profile and usage routes
- Provider-specific rerank, score, classify, tokenize, detokenize, and MCP routes

`GET /v1/models` and `GET /v1/models_detailed` were publicly readable when inspected. Model records are dynamic and may include `status`, `has_service`, `started_at`, and `expires_at`. This behavior is observational, not a stability guarantee.

### 3.2 Assumptions for v1

1. Every configured upstream key is legitimately issued to and controlled by the operator.
2. Pooling those keys is allowed by the operator's university and SwissAI usage policies.
3. Keys normally have equivalent model access; model-specific denials are treated as request/model failures unless evidence identifies a key-specific permission failure.
4. SwissAI returns standard HTTP statuses and an OpenAI-style error envelope for most failures.
5. Successful completion responses include usage when the serving model supports it. Missing usage remains unknown; it is never converted to zero.
6. `/v1/responses` continuation identifiers may be scoped to the key that created them. The proxy therefore preserves hard continuation affinity.
7. No CI or automated test may require a real SwissAI key.

### 3.3 Required validation before production release

A maintainer with an authorized key must capture sanitized fixtures for:

- Successful and failed non-streaming Chat Completions.
- Successful streaming Chat Completions, including terminal usage.
- Responses API with and without `previous_response_id`.
- 401, 403, 408, 429, 500, 502, 503, and 504 responses where reproducible.
- `Retry-After` and any SwissAI-specific rate-limit/reset headers.
- `/v1/profile` and `/v1/profile/usage` response shapes.
- Whether response/conversation identifiers remain valid when the next turn uses a different key.

Unknown behavior must fail conservatively and must not be inferred from ChatGPT-specific code.

## 4. Goals

### G1 — Pool SwissAI keys

Operators can add, name, pause, replace, probe, and delete multiple encrypted SwissAI API keys from the dashboard.

### G2 — Expose a stable OpenAI-compatible endpoint

OpenAI-compatible clients can use `http://127.0.0.1:2455/v1` without knowing which upstream key serves a request.

### G3 — Balance concurrent traffic

Fresh requests prefer the eligible key with the lowest current in-flight pressure. Round-robin tie-breaking prevents one key from receiving every simultaneous request.

### G4 — Fail over safely

Before output is committed, retryable upstream statuses and transport timeouts cause the current key to be excluded and another eligible key to be attempted, within a bounded request budget.

### G5 — Preserve observable operations

Operators can see requests, attempts, selected key aliases, token usage, latency, cooldowns, and failure reasons without exposing raw credentials or prompt bodies.

### G6 — Retain codex-lb deployment quality

The fork retains one-command local/Docker startup, dashboard authentication, SQLite by default, PostgreSQL for multi-replica deployments, health endpoints, metrics, graceful shutdown, migrations, and documented backup/restore behavior.

## 5. Non-goals

- Acquiring, generating, sharing, or scraping SwissAI keys.
- Evading university, SwissAI, model-owner, or per-user usage policies.
- Guaranteeing higher throughput than SwissAI permits.
- Retrying indefinitely or defeating `Retry-After`.
- Aggregating provider quota that SwissAI does not expose.
- Translating arbitrary Chat Completions requests into Responses requests or vice versa.
- Emulating `/responses/compact`, WebSockets, files, images, audio, or realtime APIs absent an upstream SwissAI contract.
- Proxying SwissAI admin endpoints.
- Supporting migration from an existing production `codex-lb` database in v1.
- Storing prompts, completions, tool arguments, or raw Authorization headers by default.
- Adding another framework or network dependency when the fork's existing stack already provides the capability.

## 6. Actors and trust boundaries

| Actor | Trust level | Capabilities |
| --- | --- | --- |
| Local operator/admin | Trusted | Manages upstream keys, client keys, dashboard settings, backups, and deployment. |
| Dashboard viewer | Semi-trusted | Reads redacted status, usage, and request metadata; cannot reveal or mutate secrets. |
| API client | Untrusted | Sends model requests using a local client API key, subject to model/key/rate policies. |
| SwissAI API | External dependency | Receives sanitized requests with exactly one selected upstream key. |
| Database | Sensitive persistence boundary | Stores encrypted upstream keys, hashed client keys, health state, and metadata. |
| Reverse proxy | Deployment-dependent | May terminate TLS; forwarded headers are trusted only from configured CIDRs. |

### Critical assets

- SwissAI upstream API key plaintext.
- Local client API key plaintext at creation time.
- Encryption key material.
- Request and usage metadata.
- Dashboard administrator credentials and sessions.

## 7. User flows

### 7.1 First run

1. Operator starts `swissai-lb` using Docker or the local package.
2. Operator opens `http://localhost:2455`.
3. Local first-run bootstrap follows codex-lb's existing dashboard-auth behavior.
4. Dashboard shows an empty “SwissAI Keys” page with an **Add key** action.
5. Operator enters a label and one `sk-rc-...` key.
6. The backend encrypts and stores the secret, probes SwissAI without running a generation, and returns only redacted metadata.
7. Operator adds additional keys.
8. Operator points Open WebUI, an OpenAI SDK, or another compatible client at `http://127.0.0.1:2455/v1`.

### 7.2 Normal request

1. Client authenticates to the proxy if client-key auth is enabled.
2. Proxy validates route, body size, model policy, and request budget.
3. Router selects an eligible SwissAI key and acquires its concurrency lease.
4. Adapter replaces the inbound Authorization header with the selected upstream key.
5. Proxy forwards the request to SwissAI.
6. On success, proxy streams or returns the upstream response without changing model content.
7. Proxy records attempt metadata and reported usage, releases the lease, and updates key health.

### 7.3 Transparent failover

1. Key A is selected.
2. Before any downstream response body is committed, SwissAI returns a retryable status or the transport hits a retryable timeout.
3. Proxy records the attempt, applies a key cooldown when appropriate, releases A's lease, and excludes A for this request.
4. Key B is selected.
5. The unchanged request is sent with B's bearer token.
6. If B succeeds, the client receives one successful response and does not receive A's intermediate error.

### 7.4 All keys unavailable

1. Router finds no active, non-cooled, non-saturated key allowed for the client.
2. Proxy returns an OpenAI-style `503` error with code `no_upstream_keys` and a bounded `Retry-After` when a known cooldown will expire.
3. The response contains a request ID but no upstream key identity or secret.

### 7.5 Operator pauses or replaces a key

- Pausing prevents new leases immediately; existing requests drain normally.
- Replacing a secret encrypts the new value, clears invalid/cooldown state, invalidates selection caches, and probes it.
- Deleting a key first makes it unroutable, waits for or safely expires leases, and then removes the secret. Request-history rows retain only a nullable key ID/label snapshot according to retention policy.

## 8. Supported proxy surface

### 8.1 Required v1 endpoints

| Downstream endpoint | Upstream endpoint | Behavior |
| --- | --- | --- |
| `GET /v1/models` | `GET /v1/models` | Cached live catalog; apply local client-key model allowlists. |
| `POST /v1/chat/completions` | `POST /v1/chat/completions` | Transparent JSON/SSE forwarding with key selection and failover. |
| `POST /v1/completions` | `POST /v1/completions` | Transparent JSON/SSE forwarding with key selection and failover. |
| `POST /v1/responses` | `POST /v1/responses` | Transparent JSON/SSE forwarding with continuation affinity. |
| `POST /v1/embeddings` | `POST /v1/embeddings` | Transparent JSON forwarding with key selection and failover. |

Trailing-slash aliases must behave identically without redirecting a streaming POST.

### 8.2 Codex-compatible aliases

For compatibility with clients already configured for codex-lb:

- `POST /backend-api/codex/responses` maps to SwissAI `POST /v1/responses` over HTTP.
- `GET /backend-api/codex/models` adapts the live SwissAI catalog to the minimum model shape required by Codex clients.
- Upstream WebSocket promotion is disabled.
- `/backend-api/codex/responses/compact` returns `501 unsupported_upstream_capability` unless SwissAI later documents a compatible endpoint.
- Codex client documentation must set `supports_websockets = false` and must not claim standalone web search or remote compaction.

A smoke test against the currently supported Codex CLI version is required before documenting Codex CLI as supported rather than experimental.

### 8.3 Explicitly unsupported in v1

- `/v1/audio/*`
- `/v1/images/*`
- `/v1/realtime` and live WebSockets
- `/v1/files/*`
- `/v1/responses/compact`
- SwissAI `/v1/admin/*`
- SwissAI profile mutation routes
- Provider-specific rerank/score/classify/tokenize/detokenize/MCP routes

Unsupported routes return a stable OpenAI-style `404` or `501`, never a route that appears successful but discards semantics.

### 8.4 Header policy

The proxy must:

- Discard the inbound `Authorization` header before upstream forwarding.
- Set `Authorization: Bearer <selected SwissAI key>` itself.
- Remove hop-by-hop headers, `Host`, inbound forwarding headers, and internal `X-SwissAI-LB-*` headers.
- Preserve safe OpenAI request headers such as content type, accept, and idempotency headers.
- Generate a proxy request ID when absent and return it in `X-Request-ID`.
- Never include the upstream secret in an error body, URL, log, trace, metric, or response header.

## 9. Key model and lifecycle

Use one domain term consistently:

- **SwissAI key:** an encrypted upstream credential used by the proxy.
- **Client key:** an optional key issued by `swissai-lb` to authenticate callers.

Do not call both concepts “API keys” without a qualifier in code or UI.

### 9.1 Canonical SwissAI key record

Minimum fields:

| Field | Purpose |
| --- | --- |
| `id` | Opaque stable identifier. |
| `name` | Operator-provided display label. |
| `secret_encrypted` | Fernet-encrypted upstream key. |
| `secret_fingerprint` | Keyed HMAC used for duplicate detection; never usable as authentication. |
| `secret_prefix` | Redacted display prefix only, e.g. `sk-rc-…7F2A`. |
| `enabled` | Manual pause/resume control. |
| `invalid_at`, `invalid_reason` | Permanent credential rejection state. |
| `cooldown_until`, `cooldown_reason` | Persisted temporary exclusion. |
| `consecutive_failures` | Backoff input, reset by success. |
| `max_concurrency` | Optional per-key admission cap. |
| `last_selected_at` | Fair tie-breaking. |
| `last_success_at` | Dashboard health. |
| `last_failure_at` | Dashboard health. |
| `created_at`, `updated_at` | Audit fields. |

Plaintext is decrypted only immediately before building an upstream request. ORM/API models must not expose `secret_encrypted` or plaintext.

### 9.2 Derived state

State is derived in this order:

1. `paused` when `enabled = false`.
2. `invalid` when `invalid_at` is set.
3. `cooling_down` when `cooldown_until > now`.
4. `active` otherwise.

A timer does not need to mutate a row from `cooling_down` to `active`; eligibility derives it from the current clock. Manual **Reactivate** clears invalid and cooldown state only after an explicit probe succeeds.

### 9.3 Lifecycle transitions

| Event | Transition |
| --- | --- |
| Add and probe succeeds | `active` |
| Add and probe returns 401 | `invalid` |
| Add and probe has transient network failure | Stored with cooldown and visible diagnostic; add operation does not lose the secret. |
| Manual pause | any routable state → `paused` |
| Manual resume | `paused` → prior derived state |
| Upstream 401 | → `invalid` until replacement or successful manual probe |
| Retryable throttling/failure | → `cooling_down` when failure is key-specific |
| Cooldown expires | derived → `active` |
| Successful request | clear transient failure count/cooldown → `active` |
| Replace secret | clear invalid/cooldown, probe new secret |
| Delete | immediately unroutable, then secret deleted after lease cleanup |

## 10. Selection and concurrency

### 10.1 Eligibility

A key is eligible only when all are true:

- It is enabled.
- It is not invalid.
- Its cooldown has expired.
- It is assigned to the authenticated client key, if assignments are configured.
- It has not already been attempted for the current request.
- It is below its effective concurrency cap.
- It satisfies any hard Responses continuation affinity.

### 10.2 Default strategy

The default strategy is **least in-flight with round-robin tie-breaking**:

1. Compute `in_flight / effective_max_concurrency` for each eligible key.
2. Choose the lowest pressure ratio.
3. Break equal scores by oldest `last_selected_at`.
4. Break any remaining tie using the existing replica-decorrelated stable salt.
5. Atomically acquire a lease and revalidate eligibility before dispatch.

This directly addresses concurrent query pressure without relying on quota percentages SwissAI may not expose.

### 10.3 Retained routing strategies

- **Least in-flight** — default and recommended.
- **Round robin** — even request distribution among eligible keys.
- **Fill first** — use a key until its cap/cooldown blocks it, then move on.
- **Single key** — debugging only; no failover to another key.

ChatGPT quota-derived strategies (`capacity_weighted`, `relative_availability`, `usage_weighted`, `reset_drain`, and `sequential_drain` as defined by ChatGPT quota windows) must not be presented with false SwissAI semantics. They may be removed from the dashboard or explicitly migrated to the closest supported strategy.

### 10.4 Admission behavior

- A key lease is acquired before opening the upstream request.
- Leases are released on success, error, timeout, client cancellation, and server shutdown.
- If another eligible key has capacity, the request moves there immediately.
- If every eligible key is saturated, the request waits in the existing bounded admission queue.
- Admission timeout returns `429 local_capacity_exhausted` with `Retry-After: 1`; it does not mark any key unhealthy.
- Multi-replica deployments must retain codex-lb's PostgreSQL/partitioning guarantees so configured caps are not multiplied silently by replica count.

## 11. Retry and rotation contract

### 11.1 Invariants

1. A single logical request never attempts the same key twice.
2. Total upstream attempts are bounded by `min(3, eligible distinct keys)` in v1.
3. Every attempt shares one absolute request deadline; retries do not reset the clock.
4. The request body is immutable across attempts except for removal/replacement of proxy-owned headers.
5. No failover occurs after response bytes have been committed to the client.
6. A hard continuation owner is never changed unless the proxy can prove the request is a self-contained replay.
7. Client cancellation never starts another attempt.
8. A failed attempt's lease is released before selecting the next key.
9. Intermediate upstream errors are logged but not sent if a later attempt succeeds.
10. The final response must never claim exactly-once upstream execution. Pre-output timeout failover has at-least-once upstream semantics.

### 11.2 Failure matrix

| Failure | Rotate? | Key state | Client behavior |
| --- | --- | --- | --- |
| Local validation error / unsupported model known locally | No | Unchanged | Return 400/403. |
| Upstream 400, 404, 409, 422 or content-policy rejection | No | Unchanged | Preserve sanitized upstream error. |
| Upstream 401 | Yes, before commitment | Mark selected key `invalid` | Try next key; surface final 401/503 if exhausted. |
| Upstream 403 with confirmed credential/permission code | Yes, before commitment | Cool down; only mark invalid when fixture-backed classification proves credential invalidity | Try next key. |
| Upstream 408 | Yes, before commitment | Short cooldown | Try next key. |
| Upstream 429 | Yes, before commitment | Cool down using `Retry-After`; default 30 seconds if absent | Try next key. |
| Upstream 500, 502, 503, 504 | Yes, before commitment | Increment transient failure/backoff | Try next key. |
| DNS failure, connection refused, connect timeout, TLS handshake failure | Yes, before commitment | Do not blame one key; record provider/network health | Refresh shared HTTP transport, then try next key within budget. |
| Response-header or first-byte timeout | Yes only before commitment and when request is not hard-owner-bound | Increment transient failure/backoff | Try next key; record possible duplicate-execution risk. |
| Non-stream body read fails before any body is sent downstream | Yes when budget and another key remain | Increment transient failure/backoff | Buffer/discard failed body and retry. |
| Streaming body fails after first downstream byte | No | Record failure | Terminate stream with protocol-appropriate error/close. |
| Stream idle timeout after output began | No | Record failure | Terminate stream; never splice output from another generation. |
| Client disconnect/cancellation | No | Unchanged unless an upstream status was already known | Cancel upstream and release lease. |
| All attempts exhausted | No | Keep per-attempt state | Return last actionable sanitized error plus request ID. |

`Retry-After` accepts delta seconds or an HTTP date. Persist a deadline bounded to a sane range (1 second to 24 hours). Never sleep through a long `Retry-After` inside one client request; cool the key and immediately try a different eligible key.

### 11.3 Timeout defaults

Reuse codex-lb's dashboard-first configuration precedence. Initial defaults:

- TCP connect: 8 seconds.
- Response header / first byte: 30 seconds.
- Whole non-stream request budget: 600 seconds.
- Stream idle after the first event: 300 seconds.
- Total distinct-key attempts: 3.

Timeouts are operator-tunable in the dashboard. The attempt limit is a code invariant in v1, not another setting.

### 11.4 Ambiguous execution warning

A POST may reach SwissAI even when the proxy times out before receiving a response. Retrying such an attempt can consume quota twice. This tradeoff is necessary to meet the requested timeout failover behavior and must be stated in the UI/docs. The proxy must never retry after any output reaches the client, where combining two generations would corrupt the protocol.

## 12. Responses continuation and affinity

SwissAI's key scoping for Responses state is not yet documented. Until proven portable:

- Record the selected key as owner of every observed Responses `response.id` and conversation identifier.
- A request carrying `previous_response_id`, a known conversation ID, or other provider-owned continuation state is hard-pinned to its recorded key.
- Soft session/cache affinity may prefer the prior key but can be abandoned before commitment.
- If a hard owner is unavailable, return `503 continuation_owner_unavailable`; do not route blindly to another key.
- A cross-key retry is allowed only if existing codex-lb replay-safety logic proves the complete request is self-contained and strips no client-owned state implicitly.
- Chat Completions requests carrying full message history are not hard-pinned.
- Owner mappings follow request-log retention and are deleted when no longer needed.

## 13. Model discovery

- Fetch `GET https://api.swissai.svc.cscs.ch/v1/models` at startup and at a five-minute refresh interval.
- Serve only records that are currently usable when `status`/`has_service` are present; tolerate standard OpenAI model objects that omit those fields.
- Preserve upstream model IDs exactly. Do not hardcode Apertus IDs because the live list changes.
- Cache the last successful catalog on disk and serve it stale for up to 24 hours during a catalog outage.
- Expose catalog age and refresh errors in the dashboard.
- Apply client-key model allowlists to the returned list and to generation requests.
- Do not infer context size, tool support, vision support, or Responses support from model names. Capability fields remain unknown unless SwissAI supplies them or an operator configures them explicitly.

## 14. Usage, request logs, and billing

### 14.1 Usage source

- Record token counts exactly as reported by the terminal upstream response/event.
- Preserve `0` as zero and missing as unknown.
- Do not retokenize prompts in v1.
- Do not claim SwissAI cost when no authoritative pricing exists. Cost displays use `—`, not `$0.00`.
- `/v1/profile/usage` integration is deferred until its schema and reset semantics are captured from an authorized account.

### 14.2 Logical request versus attempts

A logical request has one row visible in ordinary request logs and zero or more attempt records.

Logical request fields include:

- Request ID, route, model, stream flag, client-key ID, timestamps, final status, attempt count.
- Final selected SwissAI key ID and a historical redacted label snapshot.
- Reported input/output/cached/reasoning tokens when available.
- End-to-end latency, first-token latency, and final error code.

Attempt fields include:

- Request ID, attempt index, opaque SwissAI key ID, start/end timestamps.
- Upstream status, timeout phase, retry classification, and whether output became visible.
- No prompt, completion, bearer token, or raw provider error containing a secret.

API/client usage limits settle once from the final logical result. Upstream attempt usage is shown separately when SwissAI reports it, so a failed duplicated attempt cannot silently distort client billing counters.

## 15. Dashboard requirements

Retain codex-lb's visual system, responsive layout, light/dark themes, authentication, roles, audit log, and core navigation patterns.

### 15.1 Overview

Show:

- Active, cooling-down, paused, and invalid SwissAI key counts.
- Requests, success rate, failover rate, tokens, TTFT, and latency.
- Recent failures grouped by classification.
- Model catalog freshness.

### 15.2 SwissAI Keys page

Adapt the existing Accounts page to show:

- Label and redacted prefix.
- Derived state and cooldown countdown.
- In-flight requests and configured cap.
- Request/token totals and recent trend.
- Last success/failure and sanitized failure reason.
- Actions: add, replace secret, probe, pause/resume, and delete.

Remove ChatGPT email, plan, workspace, quota windows, reset credits, OAuth expiry, reauthentication, warmup, and auth export controls.

### 15.3 Client Keys / APIs page

Retain codex-lb's downstream client-key lifecycle, model allowlists, token limits, expiry, revocation, request trends, and assignment controls. Rename account assignments to **Allowed SwissAI keys**.

### 15.4 Request Logs and Reports

Retain filters and exports for time, model, client key, upstream key, status, and route. Add attempt count/failover reason. Raw keys and prompt content are never columns or export fields.

### 15.5 Settings

Retain applicable dashboard auth, firewall, database, retention, metrics, telemetry consent, and timeout settings. Routing settings expose only strategies with truthful SwissAI semantics. Remove settings whose only purpose is ChatGPT OAuth, quota resets, compact, upstream WebSockets, or subscription plans.

## 16. Dashboard management API

Use the existing authenticated dashboard conventions, CSRF protection, permissions, error format, and audit service.

Minimum routes:

```text
GET    /api/swissai-keys
POST   /api/swissai-keys
PATCH  /api/swissai-keys/{id}
POST   /api/swissai-keys/{id}/probe
POST   /api/swissai-keys/{id}/pause
POST   /api/swissai-keys/{id}/resume
DELETE /api/swissai-keys/{id}
```

Create request:

```json
{
  "name": "Research key A",
  "apiKey": "sk-rc-...",
  "maxConcurrency": 4
}
```

Response example:

```json
{
  "id": "sak_01...",
  "name": "Research key A",
  "keyPrefix": "sk-rc-…7F2A",
  "status": "active",
  "cooldownUntil": null,
  "maxConcurrency": 4,
  "lastSuccessAt": null,
  "lastFailureAt": null
}
```

The plaintext `apiKey` is accepted only on create or explicit replacement and is never returned. Omitting `apiKey` in a patch keeps the current secret.

## 17. Configuration and packaging

### 17.1 Names

Rename user-facing and package identifiers:

- Project/package/CLI: `swissai-lb`
- Environment prefix: `SWISSAI_LB_`
- Default data directory: `~/.swissai-lb` on host, `/var/lib/swissai-lb` in Docker
- Default container name/volume examples: `swissai-lb`, `swissai-lb-data`
- Default port: `2455` for codex-lb client-config parity

### 17.2 Bootstrap configuration

Document only settings operators commonly need:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SWISSAI_LB_DATA_DIR` | host/container defaults above | DB, encryption key, cache, archives. |
| `PORT` | `2455` | Host listen port. |
| `SWISSAI_LB_DATABASE_URL` | SQLite in data dir | PostgreSQL deployment. |
| `SWISSAI_LB_ENCRYPTION_KEY_FILE` | generated in data dir | Shared secret encryption key. |
| `SWISSAI_LB_DASHBOARD_AUTH_MODE` | `standard` | Dashboard auth mode. |
| `SWISSAI_LB_UPSTREAM_BASE_URL` | `https://api.swissai.svc.cscs.ch/v1` | Testing/self-hosted compatible gateway override. |

Runtime behavior settings belong in the dashboard, following codex-lb precedence: code default < environment fallback < non-null dashboard value.

### 17.3 First-run Docker example

```bash
docker volume create swissai-lb-data
docker run -d --name swissai-lb \
  -p 2455:2455 \
  -v swissai-lb-data:/var/lib/swissai-lb \
  ghcr.io/<owner>/swissai-lb:latest
```

Keys are added through the authenticated dashboard. Do not place real keys in image layers or committed Compose files.

### 17.4 Client example

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:2455/v1",
    api_key="sk-sailb-...",  # local client key; not a SwissAI upstream key
)

response = client.chat.completions.create(
    model="<id returned by GET /v1/models>",
    messages=[{"role": "user", "content": "Hello"}],
)
```

Open WebUI uses the same local base URL and local client key.

## 18. Architecture

Keep the fork's existing stack unless removal of dead ChatGPT code makes a dependency unnecessary:

- FastAPI/Python backend.
- React/TypeScript/Vite frontend.
- SQLAlchemy/Alembic with SQLite and PostgreSQL.
- Existing cryptography, dashboard auth, audit, middleware, metrics, and request-log infrastructure.
- Existing Rust egress only if it provides measurable value for the retained HTTP/SSE surface; ChatGPT-specific WebSocket/Responses machinery should not be carried merely for parity.

### 18.1 Dependency direction

```text
HTTP routes
  -> request/auth policy
  -> SwissAI routing service
       -> key selector + lease owner
       -> retry classifier
       -> SwissAI HTTP/SSE adapter
  -> usage/request-log settlement
  -> dashboard projections
```

Rules:

- Provider quirks stay in the SwissAI adapter.
- Selection and retry policy do not import FastAPI or frontend types.
- Secret decryption occurs in the adapter immediately before dispatch.
- Request logs receive redacted facts, never transport objects or plaintext credentials.
- Time and sleep use the existing clock/scheduler seams so cooldown and timeout tests use virtual time.

### 18.2 Reuse from codex-lb

Prefer adapting these existing concepts over building parallel versions:

- Account/key selection cache and atomic lease lifecycle.
- `failover_decision` policy shape and downstream-visibility guard.
- OpenAI error parsing/sanitization.
- Model-source HTTP/SSE forwarding and bounded timeouts.
- Client API keys, limits, assignments, and usage reservation settlement.
- Dashboard authentication, permissions, firewall, audit, retention, and metrics.
- Request log/report projections.
- Docker, Helm, migration, health, and graceful-shutdown infrastructure.

Delete ChatGPT-specific branches after the SwissAI path has equivalent tests. Do not leave two competing routing cores.

## 19. Security requirements

1. Retain the upstream MIT license and copyright notice; add fork attribution and a SwissAI affiliation disclaimer.
2. Encrypt upstream keys at rest using the existing encryption-key lifecycle.
3. Hash local client keys; show plaintext only once at creation.
4. Redact `authorization`, `api_key`, `token`, `secret`, and known key values recursively from logs, audits, traces, and upstream errors.
5. Never expose upstream keys through an export endpoint.
6. Dashboard mutations require write permission, CSRF protection, and audit entries.
7. Remote proxy routes require client-key auth unless the existing local-only firewall exception applies.
8. Forwarded IP headers are ignored unless the immediate peer is in configured trusted-proxy CIDRs.
9. Reject upstream base URLs containing userinfo; allow only absolute `https` by default. Plain HTTP is permitted only for explicit development/test configuration.
10. Block proxying to link-local, loopback, or private addresses when the base URL is changed remotely, unless an operator-local bootstrap setting explicitly permits it; prevent SSRF through dashboard configuration.
11. Bound request body, SSE frame, buffered response, queue, retry, and timeout resources.
12. Do not log prompts or completions by default.
13. Database backups include encrypted secrets and must be protected together with the encryption key; losing the key makes stored upstream credentials unrecoverable.
14. Dependency and container scans remain release gates.

## 20. Observability

### 20.1 Structured logs

Each logical request and attempt includes:

- `request_id`
- route and model
- attempt index
- opaque/redacted upstream key ID
- selection strategy
- in-flight count
- status/failure class/timeout phase
- failover action
- downstream-visible boolean
- latency and token usage when known

Never log secret prefixes long enough to authenticate or identify the full credential.

### 20.2 Metrics

Minimum bounded-cardinality metrics:

```text
swissai_lb_requests_total{route,outcome}
swissai_lb_upstream_attempts_total{route,outcome,status_class}
swissai_lb_failovers_total{reason}
swissai_lb_eligible_keys
swissai_lb_key_inflight{key_id}
swissai_lb_key_state{key_id,state}
swissai_lb_upstream_latency_seconds{route}
swissai_lb_upstream_ttft_seconds{route}
swissai_lb_admission_wait_seconds
swissai_lb_model_catalog_age_seconds
```

No model-independent high-cardinality error message, email, key prefix, prompt, response ID, or request ID belongs in metric labels.

### 20.3 Health

- `/health/live`: process/event loop alive; no upstream dependency.
- `/health/ready`: schema ready, encryption key usable, and routing service initialized. An empty key pool is reported in details but does not make the dashboard process unready.
- Dashboard shows a provider outage separately from all-keys-invalid.

## 21. Data migration and compatibility

- v1 targets fresh `swissai-lb` data directories.
- Starting against a `codex-lb` database must fail with an actionable message rather than mutate it in place.
- Alembic migrations are required for every schema change and must support SQLite and PostgreSQL.
- The old `CODEX_LB_*` environment prefix is not silently accepted, preventing accidental use of production codex-lb secrets/configuration.
- The fork keeps an `upstream` Git remote and records the baseline commit in release notes.
- Future upstream merges must be reviewed by subsystem; ChatGPT-specific behavior is not reintroduced automatically.

## 22. Testing strategy

### 22.1 Unit tests

- Failure classification for every row in the retry matrix.
- `Retry-After` parsing and deadline bounds.
- Derived key-state transitions with a fake clock.
- Least-in-flight and round-robin selection.
- Exclusion of already-attempted keys.
- Hard continuation affinity.
- Header sanitization and secret redaction.
- Model-catalog filtering and stale-cache behavior.

### 22.2 Property/invariant tests

Name and enforce at least:

- `SECRET_NEVER_LEAVES_TRUST_BOUNDARY`
- `ONE_KEY_AT_MOST_ONCE_PER_REQUEST`
- `ATTEMPTS_NEVER_EXCEED_BUDGET`
- `NO_FAILOVER_AFTER_DOWNSTREAM_VISIBILITY`
- `HARD_OWNER_NEVER_CHANGES_UNPROVEN`
- `EVERY_ACQUIRED_LEASE_IS_RELEASED`
- `CLIENT_USAGE_SETTLES_AT_MOST_ONCE`
- `PAUSED_OR_INVALID_KEY_IS_NEVER_SELECTED`
- `COOLDOWN_SURVIVES_RESTART`

### 22.3 Integration tests with a fake SwissAI server

Cover JSON and SSE variants:

1. A succeeds on first attempt.
2. A returns 429 and B succeeds; A enters cooldown.
3. A returns 429 with `Retry-After`; deadline is persisted and honored.
4. A connect-times out and B succeeds.
5. A returns 503 and B succeeds.
6. A returns 401; A becomes invalid and B succeeds.
7. A returns 400; B is never called.
8. A starts streaming then disconnects; B is never called.
9. All keys fail; final sanitized error and attempt count are correct.
10. Client disconnect cancels upstream and releases the lease.
11. Concurrent requests distribute across keys and obey caps.
12. A hard-bound Responses continuation never changes key.
13. Model catalog outage serves a bounded stale cache.
14. Restart preserves encrypted keys and cooldown state.
15. Client-key assignments and model allowlists restrict selection.

### 22.4 End-to-end tests

- OpenAI Python SDK: models, Chat Completions stream/non-stream, Responses stream/non-stream, embeddings.
- Open WebUI basic chat against the local endpoint.
- Dashboard: add, invalid add, replace, pause, resume, probe, delete.
- SQLite single-instance and PostgreSQL multi-replica routing.
- Docker fresh-start, persistence, backup, and restore.
- Current Codex CLI smoke test before marking its alias stable.

### 22.5 Load and fault tests

- Burst traffic above one key's cap distributes without lease leaks.
- One key returns persistent 429 while others remain healthy.
- Whole SwissAI host is unreachable; attempts stay bounded and no key is falsely invalidated.
- Slow first byte and mid-stream stalls follow different retry rules.
- Process shutdown drains active streams within the configured bound.

No test fixture may contain a real key.

## 23. Acceptance criteria

### AC1 — First-run success

**Given** a fresh deployment and one valid SwissAI key\
**When** the operator adds the key and sends a Chat Completions request\
**Then** the request succeeds through `http://127.0.0.1:2455/v1`, usage is logged when reported, and the plaintext key appears nowhere after the create request completes.

### AC2 — Concurrent balancing

**Given** three active keys with equal caps\
**When** at least three requests overlap\
**Then** selection prefers unused capacity and does not send all requests to the same key.

### AC3 — Rate-limit rotation

**Given** A returns 429 before output and B is healthy\
**When** a request selects A\
**Then** A enters cooldown, B receives the unchanged request, and the client receives B's successful response only.

### AC4 — Timeout rotation

**Given** A exceeds the configured pre-output timeout and B is healthy\
**When** the request is not hard-owner-bound\
**Then** A's attempt is closed, its lease is released, B is attempted within the original deadline, and the possible duplicate-execution risk is observable.

### AC5 — No stream splicing

**Given** A has emitted any response byte to the client\
**When** A disconnects or goes idle\
**Then** B is never attempted and the stream ends with the appropriate error/close behavior.

### AC6 — Invalid credential isolation

**Given** A returns a confirmed authentication 401 and B is healthy\
**When** failover succeeds through B\
**Then** A remains invalid across restart until replaced or successfully re-probed.

### AC7 — Continuation safety

**Given** a Responses continuation owned by A\
**When** A is unavailable\
**Then** the proxy returns `continuation_owner_unavailable` and does not send the continuation to B without a proven self-contained replay.

### AC8 — Secret safety

**Given** representative success, failure, audit, trace, export, and exception paths\
**When** logs, metrics, database API responses, and dashboard payloads are inspected\
**Then** no SwissAI key plaintext is present.

### AC9 — Bounded failure

**Given** five configured keys and a provider-wide outage\
**When** one client request is made\
**Then** no more than three distinct upstream attempts occur, all leases are released, and the request ends within its absolute budget.

### AC10 — Operational parity

**Given** Docker/SQLite and Kubernetes/PostgreSQL deployments\
**When** health checks, migrations, dashboard auth, request routing, graceful shutdown, backup, and restore are exercised\
**Then** retained codex-lb operational contracts continue to work under the renamed configuration surface.

## 24. Success metrics

- 100% of retryable pre-output 429/5xx test failures fail over when another eligible key exists.
- 0 retries after downstream visibility in fault-injection tests.
- 0 plaintext upstream keys found by secret-scanning logs, traces, responses, exports, and fixtures.
- 0 leaked leases after cancellation, timeout, or shutdown suites.
- Proxy-added latency below 25 ms p95 in a local no-contention benchmark, excluding upstream time.
- Model catalog refresh recovers automatically and never serves stale data beyond the configured 24-hour ceiling.
- All retained upstream lint, typecheck, unit, integration, frontend, migration, and container gates pass.

## 25. Implementation plan

Each phase must be reviewable and independently verified.

### Phase 0 — Establish the fork

- Fork with full Git history; add `upstream` remote.
- Pin and record the baseline commit.
- Retain MIT license/copyright; add fork attribution and non-affiliation notice.
- Rename package, CLI, image, data directory, env prefix, docs, and visible branding.
- Add a CI check rejecting stale user-visible `codex-lb`/ChatGPT branding except attribution/migration docs.
- Verify unchanged upstream tests before provider work.

### Phase 1 — SwissAI key domain

- Add SwissAI key persistence, encryption, repository, service, schemas, management API, and audit events.
- Adapt Accounts UI into SwissAI Keys UI.
- Add probe using a non-generation authenticated endpoint.
- Remove plaintext from every response path.
- Verify lifecycle, redaction, SQLite/PostgreSQL migrations, and frontend flows.

### Phase 2 — Single-key forwarding

- Isolate SwissAI HTTP/SSE adapter using existing model-source forwarding code.
- Implement required `/v1` routes and model discovery.
- Forward successful JSON/SSE responses faithfully.
- Add usage/request-log settlement.
- Verify with the fake SwissAI server and OpenAI SDK.

### Phase 3 — Selection, leases, and failover

- Adapt one existing selection/lease core to SwissAI keys.
- Implement least-in-flight routing and retained strategies.
- Implement the failure matrix, cooldown persistence, attempt records, and absolute budgets.
- Add continuation ownership and downstream-visibility gates.
- Run property, cancellation, fault, concurrency, and multi-replica tests.

### Phase 4 — Dashboard and operations

- Adapt overview, requests, reports, settings, client-key assignments, metrics, and health diagnostics.
- Remove/hide unsupported ChatGPT capabilities and settings.
- Update Docker, Compose, Helm, backup, remote-access, and troubleshooting docs.
- Capture dashboard screenshots required by the upstream contribution rules.

### Phase 5 — Cleanup and release

- Delete dead OAuth, refresh, ChatGPT usage, reset-credit, compact, WebSocket bridge, files/images/realtime, and subscription-only code after replacement coverage exists.
- Remove now-unused dependencies and migrations only when safe for fresh-fork history; do not rewrite applied migration history casually.
- Run full test/type/lint/build/security/container/load suites.
- Perform an authorized live canary with one key, then two keys with injected proxy failures.
- Publish a beta image before a stable release.

## 26. Rollout and rollback

### Rollout

1. Fake-upstream CI only.
2. Local canary with one authorized key.
3. Local canary with two keys and low concurrency.
4. Validate real 401/429/timeout fixtures and continuation behavior.
5. Docker beta with a new empty data volume.
6. PostgreSQL multi-replica beta.
7. Stable release only after policy authorization and secret-leak review.

### Rollback

- Back up the database, encryption key, and configuration before every upgrade.
- Roll back application image and database migration together.
- Never roll back only the encryption key.
- If routing is suspect, pause all but one known-good key or switch to **Single key** before downgrading.
- A failed SwissAI deployment must not modify a codex-lb data directory.

## 27. Demo script

1. Start `swissai-lb` in Docker.
2. Add three redacted test keys backed by a fake SwissAI server.
3. Show all three as active in the dashboard.
4. Run six overlapping streaming Chat Completions requests and show in-flight distribution.
5. Configure fake key A to return 429 with `Retry-After: 60`.
6. Send another request; show transparent success through B and A cooling down.
7. Configure B to connect-timeout; show success through C and a two-attempt request log.
8. Begin a stream through C, emit one token, then disconnect upstream; show that no other key is attempted.
9. Pause C and show selection excludes it.
10. Display request logs, usage, metrics, and audit entries without revealing any key plaintext.

## 28. Open questions

These do not block the written design but must be resolved at the stated gates:

1. **Rate-limit contract:** Which headers/error codes distinguish concurrency throttling, per-key quota, per-user quota, and provider-wide overload?
2. **Continuation scope:** Are Responses IDs and conversation objects portable between keys? Until proven, hard affinity remains mandatory.
3. **Usage:** What stable schema and reset semantics does `/v1/profile/usage` provide?
4. **Capabilities:** Does every live model support Chat Completions, Responses, streaming, tools, and embeddings, or is capability metadata available elsewhere?
5. **Codex CLI:** Does current Codex operate reliably against SwissAI `/v1/responses` without remote compact or WebSockets?

## 29. References

- codex-lb source: <https://github.com/Soju06/codex-lb>
- codex-lb documentation: <https://soju06.github.io/codex-lb/>
- codex-lb routing guide: <https://soju06.github.io/codex-lb/routing/>
- SwissAI Research Platform: <https://serving.swissai.svc.cscs.ch/>
- SwissAI Open WebUI guide: <https://serving.swissai.svc.cscs.ch/guides/01-getting-started/openwebui>
- SwissAI API base: <https://api.swissai.svc.cscs.ch/v1>
- SwissAI live OpenAPI document: <https://api.swissai.svc.cscs.ch/openapi.json>
- SwissAI model-launch: <https://github.com/swiss-ai/model-launch>
