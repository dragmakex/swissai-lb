# SwissAI operations

Normative owner: [SwissAI key-pool specification](spec.md). Current delivery cleanup: [change specification](../../changes/trim-unused-delivery-tooling/specs/swissai-key-pool/spec.md).

## Surface

Supported: `GET /v1/models`, `POST /v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/embeddings`. POST trailing slashes are handled directly, without redirecting a generation. `/backend-api/codex/responses` and `/backend-api/codex/models` are experimental HTTP aliases.

Files, audio, images, realtime, compact and upstream admin operations return an explicit unsupported error. ChatGPT account import, OAuth and refresh routers are not installed. Old provider-specific source files and tests remain in the fork history/worktree while replacement coverage is built; they are not a second active inference path.

## Keys and routing

Upstream secrets are SwissAI keys (`sk-rc-…`). Local caller credentials are client keys (`sk-sailb-…`), shown once and hashed at rest. Model/key assignments and expiry apply when client-key authentication is enabled.

Key add/replace and the Probe action check the inference gateway, not `/v1/profile`. The provider's account-profile access-token boundary rejects research inference keys; its public model list also cannot validate credentials. The probe sends an intentionally unnamespaced sentinel model with empty messages and recognizes the observed authenticated model-not-found rejection. No real model is selected and no completion is generated. A generic HTTP error or unexpected success is inconclusive and does not change key health; an inference 401 still invalidates a credential.

If keys were incorrectly marked invalid by the old profile probe, restart the Python process (or rebuild/restart the Docker image), then click **Probe** on each saved key. An authenticated re-probe clears the stale invalid state through the generation-fenced repository operation; do not delete/re-enter keys, replace `encryption.key`, or edit the database manually. This proves authentication, not model availability, allowance or live generation compatibility.

Least in-flight is the default. Round robin, fill first and an explicit single-key debug strategy are available. Admission uses persisted, atomically acquired capacity leases. Leases are renewed every 20 seconds and expire after 90 seconds if their process disappears; losing renewal cancels the owner rather than silently exceeding capacity.

429 honors a bounded `Retry-After` (delta seconds or HTTP date). 401 invalidates a credential. 408 and 500/502/503/504 allow pre-output retry. Unknown 403, request/model/policy errors do not rotate. A logical request never retries a key and never exceeds three distinct attempts.

**Execution is at least once.** A timeout before output can mean SwissAI executed the first POST. Failover may consume usage twice. After headers/output are committed, the proxy never sends another generation into that stream.

Pausing blocks new leases and lets existing requests drain. Deleting an active key pauses it and returns a drain conflict; retry deletion once in-flight requests are finished. Replacing a key increments its secret generation. Old continuations cannot silently move to the new credential.

## Auth modes and networks

The host launcher defaults to loopback. To serve the LAN, bind `--host 0.0.0.0` and explicitly set `SWISSAI_LB_PROXY_ALLOW_ANONYMOUS_LAN=true` if anonymous inference is desired. Private socket peers are allowed in that mode. Otherwise enable client-key authentication and issue local client keys through the dashboard. The auth toggle overrides anonymous LAN admission.

Dashboard passwords, roles, session security, CSRF, TOTP and trusted reverse-proxy behavior come from upstream. The generated bootstrap token is written to `bootstrap.token` in the data directory with mode 0600 rather than printed in logs. `SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN` supports secret-backed initial remote setup. Configure trusted proxy peers explicitly; never trust arbitrary forwarded IP headers.

Only bootstrap configuration can change the upstream destination. HTTPS is required unless an operator explicitly enables `SWISSAI_LB_ALLOW_INSECURE_UPSTREAM` for a fake local server. URLs containing userinfo, query or fragments are rejected. No dashboard endpoint accepts an arbitrary upstream URL.

## Storage and migration

The default host data directory is `~/.swissai-lb`; Docker uses `/var/lib/swissai-lb`. `SWISSAI_LB_DATABASE_URL` selects PostgreSQL. Every replica must mount the same encryption key. The upstream startup fingerprint check rejects mismatched keys.

Alembic remains authoritative. The SwissAI revision follows the pinned upstream head; it adds key health, leases, attempts, continuations and pool settings without rewriting upstream migrations. Existing upstream and earlier prototype databases are deliberately refused. Start with a fresh database/volume.

Back up the database, encryption key and bootstrap configuration together. Use the inherited SQLite backup machinery for live SQLite snapshots; do not copy only `store.db` while WAL writes are active. Test restoration into a separate fresh directory and verify that encrypted keys, invalid/cooldown state and dashboard access survive. Never restore only an old encryption key.

## Optional telemetry

Anonymous telemetry is inactive until a persisted dashboard decision or explicit environment setting enables it. Review the payload and collector documentation first: the retained telemetry protocol and default collector use an external shared service, not a newly provisioned SwissAI LB service. `SWISSAI_LB_TELEMETRY_ENDPOINT` selects the collector. Declining the first prompt sends nothing; disabling previously active telemetry sends one anonymous opt-out notice. Shutdown closes task admission and drains these notices alongside audit and fleet work before closing shared clients.

## Usage and observability

The proxy stores metadata only: logical request, HTTP route, stream mode, attempt facts, historical key labels, status, timing and reported token usage. The request-log key selector uses the retained `accountId` query parameter as a compatibility name for SwissAI source IDs; route text is searchable. Deleted keys retain their attempt-time labels in history. It does not store prompts, output text or tool arguments. Requests settle local token limits once, independently of failover attempts. When upstream usage is missing, token counters stay unknown; limited clients are conservatively charged against the admission budget rather than silently refunded. These reservation estimates are not provider-reported usage.

SwissAI pricing is unknown. Cost/credit limits are not offered. Detailed request-log costs remain null. The UI displays `—` instead of inventing a price. Historical report aggregation APIs retain some numeric upstream summary contracts; those are not authoritative SwissAI billing.

`/health/live` is process-local. `/health/ready` checks initialized storage and drain state, without evicting pods for a provider outage. `/metrics` exposes actual SwissAI request/attempt/failover/lease/state/latency/catalog observations. Metric labels never include prompts, bearer values, response IDs or request IDs.

The retention control governs request logs, attempts, audit rows and continuation mappings. Zero disables retention; choose at least 30 days to enable it. Cleanup uses short batches rather than one long database transaction. Attempt facts remain while their logical request is retained by the history-fold safety gate, preserving historical labels and retry diagnostics. The retained 15-minute usage/report fold scheduler is owned by the SwissAI lifespan; source-key identities survive raw and folded report reads.

The keys page reports seven UTC calendar days of attempted requests, daily activity and observed terminal input/output tokens. A failover contributes an attempt to each key it used, but terminal usage belongs only to the final key. Missing usage stays unknown; a reported zero stays zero, with observation coverage shown explicitly. Metrics scraping reads lightweight key snapshots, not seven-day usage aggregates, and eligibility accounts for health, remaining capacity and single-key routing.

The dashboard's quality band describes the current visible, filtered request-log page, not a pool-wide rate. Its CSV button exports that same page through an explicit metadata allowlist. Unknown usage stays blank, reported zero stays zero, and untrusted string cells are protected against spreadsheet formulas. Conversation summaries do not interpret inherited numeric cost aggregates as authoritative SwissAI prices.

Remote bootstrap instructions identify `SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN` or `bootstrap.token` in the server data directory. The token is not emitted in logs. Existing reverse-proxy and other environment hints use the fork namespace too.

Streaming observations accept terminal usage rather than preliminary creation counters. First-token timing measures the first observed text, reasoning or tool-call output; metadata-only streams leave that timing unknown. A terminal Responses failure remains a failed logical outcome even when its HTTP transport status is 200. Interrupted committed output cannot obtain a local quota refund merely because terminal usage is missing. These conservative local charges are not inserted into provider token metadata.

Ownership inspection is bounded to 16 identifiers of at most 512 characters per logical request; credential-like identifiers are refused rather than persisted. Stream bytes remain transparent for accepted provider payloads.

## Fork identity and release history

Runtime, frontend and project metadata use `0.1.0-beta.1`; Python distributions and the lockfile normalize this to `0.1.0b1`. A retained storage/package regression checks runtime, Python/frontend metadata and the single SwissAI lock entry together.

Upstream release/publishing helpers, manifests and maintainer bots are removed. First fork publication still requires explicit maintainer authorization, a repository/tag baseline and release evidence. No published fork image or completed stable release is implied. Upstream history and attribution remain in Git and LICENSE.

## Simple laptop / VPS deployment

The normal deployment is one Python process serving the React assets and inference routes, with SQLite and its encryption key in one persistent data directory. From source, build the frontend once with Bun and run `uv run swissai-lb --host 127.0.0.1 --port 2455`. A prebuilt wheel/image already includes those assets; no frontend server runs beside Python. No Rust compiler, native worker, PostgreSQL, Nix or Kubernetes is required.

For a laptop or VPS, `docker compose up -d --build` starts only `server`. Docker Compose 2.24+ accepts the optional `.env.local`; no local env file is required. The named volume remains `swissai-lb-data` and HTTP binds to loopback. For example, `ssh -N -L 2455:127.0.0.1:2455 user@your-vps` exposes that loopback listener securely to a laptop; alternatively put it behind a correctly configured TLS reverse proxy. Set a dashboard password, add SwissAI keys, create local client keys and enable client-key authentication. Anonymous LAN inference stays opt-in.

Keep the data volume on upgrades and use `docker compose down` without `-v` to stop. Back up SQLite using its live-backup API and save `encryption.key` alongside it, as described above. Loss of that key makes saved credentials unreadable. Vite is only in the explicit `dev` profile; PostgreSQL is only in its explicit profile or an operator-configured external connection.

The unused Rust workspace, worker and Python IPC/native dispatch branches are removed rather than hidden behind flags. Shared Python protocol/golden fixtures survive under `tests/fixtures/protocol`. The generated React components remain; unused shadcn/react-doctor CLIs and their unused CSS import are removed, not the application's lint/type/test checks.

`make ci` / `make ci-fast` require no Rust, cluster or external database. `make ci-extended` adds retained integration/database and standard-image checks. Helm/kind, Nix/bun2nix, distroless, the separate production Compose file and the old MkDocs site are removed, not dormant optional delivery modes. The short root README links this operational context, the [generated settings reference](../configuration-tiers/reference.md) and [dashboard login recovery](../admin-auth/ops.md).

## Optional database and release gates

The standard Docker build still builds the real React frontend. It is the only shipped container build; use a locally built image, not an assumed published fork tag. An OCI-compatible laptop container engine still needs working host networking; building an image alone is not a reachable deployment check. Native Python remains the straightforward laptop path.

SQLite remains single-process under the inherited startup lock. Optional PostgreSQL coordination and its two-real-process/backup tests remain; do not multiply replicas against SQLite or use different encryption keys. Previous chart-managed tests are historical evidence in the earlier ledgers, not a promise that this fork still supplies Kubernetes packaging. Runtime `/metrics` remains available without chart-owned alerts or dashboards.

Before stable release: authorized SwissAI fixtures and canary, supported-client/streaming smoke tests, retained Python/frontend and provider/control-plane checks, standard container/migration checks, backup/restore, bounded fault/load verification and secret/dependency/container scans. Focused live requests do not replace those gates. Record evidence in the [fork ledger](../../changes/swissai-key-pool/tasks.md).
