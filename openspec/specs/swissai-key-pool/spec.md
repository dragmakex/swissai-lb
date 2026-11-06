# SwissAI Key Pool

## Purpose

Provide SwissAI bearer-key pooling through the retained codex-lb dashboard and operational controls, without implying support for ChatGPT-only capabilities.

## Requirements

### Requirement: SwissAI-only inference surface
The proxy SHALL expose models, Chat Completions, Completions, Responses and embeddings over HTTP. POST trailing-slash aliases SHALL preserve semantics without redirects. Unsupported provider capabilities SHALL return an explicit unsupported error. OAuth, token refresh and upstream WebSocket inference SHALL NOT be registered.

#### Scenario: Unsupported compact operation
- **WHEN** a client calls `/v1/responses/compact`
- **THEN** the proxy returns `501 unsupported_upstream_capability` without contacting SwissAI

#### Scenario: Trailing slash generation
- **WHEN** a client posts to `/v1/responses/`
- **THEN** the proxy forwards the same JSON body without redirecting the POST

### Requirement: Consistent fork identity
Runtime, Python package, frontend and chart versions SHALL identify the SwissAI fork consistently. Release tooling SHALL resolve package and chart identities from project metadata, including when inspecting historical upstream references. Operator configuration SHALL use the `SWISSAI_LB_` namespace.

#### Scenario: Bootstrap guidance identifies the secret source
- **WHEN** a remote operator sets the initial dashboard password
- **THEN** the UI directs them to `SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN` or the data directory's `bootstrap.token` file without claiming the secret is logged

#### Scenario: Inspect a fork release candidate
- **WHEN** release tooling reads the current SwissAI project
- **THEN** it validates the SwissAI lockfile entry and chart without requiring removed codex-lb paths

### Requirement: Retained operator dashboard
The dashboard SHALL retain the upstream React layout, themes, authentication, roles, client keys, request logs and reports. It SHALL provide add, replace, probe, pause, resume and delete actions for SwissAI keys and SHALL NOT present subscription quota, OAuth or upstream WebSocket controls as SwissAI features.

#### Scenario: Manage an encrypted credential
- **WHEN** an authorized writer adds and then pauses a SwissAI key
- **THEN** its redacted metadata appears in the existing dashboard and new requests cannot select it

#### Scenario: Export visible request metadata safely
- **WHEN** an operator exports the visible request-log page
- **THEN** CSV includes only its allowlisted request metadata, preserves missing values and reported zeroes, and prevents spreadsheet-formula execution from metadata strings

#### Scenario: Inspect recent routing quality
- **WHEN** an operator views a request-log page
- **THEN** success/failover rates, observed first-token and overall latency, and grouped failure classifications identify that visible page as their sample rather than claiming pool-wide rates

#### Scenario: Inspect and filter SwissAI request history
- **WHEN** an operator inspects requests for a SwissAI key or searches an HTTP route
- **THEN** the log identifies the route, stream mode and historical key label and returns only matching requests

### Requirement: Per-key activity facts
The keys page SHALL show seven UTC calendar days of per-key attempts, daily request activity and reported terminal input/output tokens. Missing token observations SHALL remain unknown and reported zero SHALL remain zero. Failover SHALL count activity for every attempted key without duplicating terminal usage across keys.

#### Scenario: Failover contributes to both keys' activity
- **WHEN** key A fails before output and key B succeeds with reported usage
- **THEN** both keys show an attempted request, but only B receives the terminal usage observation

### Requirement: Separate upstream and client credentials
SwissAI credentials SHALL be encrypted at rest, deduplicated by keyed fingerprint and excluded from response schemas, logs and exports. Local client credentials SHALL be hashed and shown only upon creation or regeneration. Error redaction SHALL remove known upstream secrets and credential-bearing fields recursively.

#### Scenario: Provider echoes its Authorization header
- **WHEN** an upstream error includes the selected credential in its error message
- **THEN** the downstream error and stored diagnostics omit the credential

### Requirement: Explicit network and client-key policy
With client-key authentication enabled, every inference and model-discovery call SHALL require a valid local client key. An explicit bootstrap option SHALL permit anonymous private-LAN socket peers only when client-key authentication is off. Forwarded headers SHALL NOT expand anonymous access. Dashboard authentication SHALL remain separate.

#### Scenario: Authentication overrides anonymous LAN
- **GIVEN** anonymous LAN admission is enabled
- **WHEN** the operator enables client-key authentication
- **THEN** a private LAN caller without a valid local client key is rejected

### Requirement: Bounded distinct-key failover
A logical request SHALL attempt each key at most once and SHALL attempt at most three distinct keys. Single-key and hard-owner requests SHALL NOT cross keys. Intermediate errors SHALL NOT be sent when a later attempt succeeds. Request content SHALL remain immutable across attempts.

#### Scenario: Rate limit followed by success
- **WHEN** key A returns 429 before output and eligible key B succeeds
- **THEN** A enters cooldown, B receives the unchanged request and the client receives only B's response

### Requirement: Shared deadline and downstream commitment
Attempts SHALL share one absolute request deadline. Connect, first-byte and stream-idle bounds SHALL be enforced. The proxy SHALL prefetch stream data before committing downstream headers and SHALL NOT retry after downstream commitment. Pre-output retry SHALL NOT imply exactly-once upstream execution.

#### Scenario: Headers arrive but stream output stalls
- **WHEN** an upstream returns success headers but exceeds the first-byte timeout
- **THEN** the proxy can try another eligible key before committing the downstream response

#### Scenario: Stream disconnects after output
- **WHEN** an upstream disconnects after response bytes have been sent downstream
- **THEN** the proxy closes the stream without trying another key

### Requirement: Owned lease lifecycle
Capacity acquisition SHALL atomically revalidate enablement, invalidity, cooldown, client assignments, affinity and caps. Acquired leases SHALL be released on success, failure, cancellation and shutdown. Cancellation SHALL NOT start another attempt. PostgreSQL replicas SHALL share admission rather than multiplying caps per replica.

#### Scenario: Caller cancels a body read
- **WHEN** a client cancels while the proxy buffers a non-stream response
- **THEN** its response and lease are closed and no new key is attempted

#### Scenario: Two replicas compete for one slot
- **WHEN** requests on two PostgreSQL-backed replicas select a key capped at one request
- **THEN** at most one holds an unexpired lease for that key at a time

### Requirement: Conservative failure classification
401 SHALL invalidate a credential. Retryable 408, 429 and 500/502/503/504 failures SHALL allow pre-output rotation. Unknown 403 and request/model/policy errors SHALL NOT rotate. Provider-wide network failures SHALL NOT invalidate a particular credential.

#### Scenario: Unclassified permission denial
- **WHEN** SwissAI returns a 403 without a fixture-backed credential-specific code
- **THEN** the proxy returns the sanitized error without rotating or cooling unrelated keys

### Requirement: Client policy and settlement
Empty restricted model or key assignments SHALL deny all access; null assignments SHALL be unrestricted. Client token limits SHALL reserve and settle once per logical request, independently of retries. Missing upstream usage SHALL remain unknown in provider usage metadata; conservative reservation estimates SHALL NOT be reported as provider token counts.

#### Scenario: Interrupted visible output does not refund unknown usage
- **WHEN** a limited client receives committed stream output before the upstream disconnects without terminal usage
- **THEN** its reservation settles conservatively once, provider usage remains unknown and no retry occurs

#### Scenario: Failover settles local usage once
- **WHEN** one request fails through A and succeeds through B with reported usage
- **THEN** the client usage counter settles once using the successful logical result

### Requirement: Continuation ownership includes credential generation
Response and conversation ownership SHALL bind to the key identity and secret generation that created them. Unknown, conflicting, replaced or unavailable owners SHALL fail closed unless self-contained replay is proven.

#### Scenario: Bound model metadata before admission
- **WHEN** a model ID is blank, non-string or over 512 characters
- **THEN** the proxy returns `400 invalid_model` before acquiring capacity or dispatching upstream

#### Scenario: Malformed continuation references fail before dispatch
- **WHEN** a request supplies a non-string, empty or over-512-character continuation reference
- **THEN** validation rejects it without silently routing the request as unpinned

#### Scenario: Owner secret is replaced
- **WHEN** a client continues a response created before the owner's credential replacement
- **THEN** the proxy returns `continuation_owner_unavailable` instead of sending the continuation using a different secret

### Requirement: Authoritative migrations and fresh-fork safety
Runtime schema changes SHALL use the upstream Alembic lifecycle. Existing codex-lb and prototype databases SHALL be rejected before mutation. Concurrent fresh-fork migration checks SHALL use the existing cross-process migration lock.

#### Scenario: Existing production database
- **WHEN** startup is pointed at an existing database without the SwissAI ownership marker
- **THEN** startup refuses to migrate it and leaves its tables and data unchanged

### Requirement: Truthful metadata and bounded retention
Missing usage SHALL remain unknown and reported zero SHALL remain zero. Detailed SwissAI request costs SHALL remain unknown without authoritative pricing. Enabled retention SHALL purge request, attempt, audit and continuation metadata in bounded batches. The catalog SHALL NOT serve data older than 24 hours.

#### Scenario: Preliminary usage is not terminal usage
- **WHEN** a Responses stream reports preliminary counts but its terminal event omits usage
- **THEN** logical provider usage remains unknown rather than adopting the preliminary counts

#### Scenario: Responses terminates with a failed result
- **WHEN** a Responses request returns a terminal failed state over HTTP 200
- **THEN** the proxy preserves the response bytes, records a failed logical outcome with any reported usage, and does not rotate or invalidate the credential

#### Scenario: Metadata arrives before generated output
- **WHEN** stream creation metadata arrives before any model text or tool-call output
- **THEN** first-token latency is recorded when model output is first observed, not when metadata arrives

#### Scenario: Logical history is retained while a fold catches up
- **WHEN** an old logical request is retained by the history-fold safety gate
- **THEN** metadata retention preserves its attempt facts and historical key label until that logical row is removed

#### Scenario: Catalog outage exceeds stale limit
- **WHEN** the last successful catalog is older than 24 hours
- **THEN** model discovery returns an availability error rather than an unbounded stale catalog

#### Scenario: Request count cache lags a newly committed row
- **WHEN** a request-log page contains more rows than the cached count implies
- **THEN** its reported total is at least the number of rows observed through that page

### Requirement: Provider-appropriate reporting
Report distribution charts SHALL use request counts rather than inferred SwissAI costs. The dashboard SHALL NOT expose subscription burn projections or account-only thread/cache-locality analytics as SwissAI measurements.

#### Scenario: Monitoring does not bypass network isolation
- **WHEN** network policy and Prometheus scraping are enabled
- **THEN** ServiceMonitor uses the served HTTP metrics endpoint and network policy does not grant all namespaces access to the application port; cross-namespace scraping requires explicit ingress peers

#### Scenario: Shipped monitoring matches the running provider
- **WHEN** operators install the Helm alerts and Grafana dashboards
- **THEN** their metric names and label selectors match the SwissAI exporter, logical failure alerts include failed HTTP-200 Responses, and SQL panels use observed SwissAI metadata without retired bridge/prewarm measurements

#### Scenario: Upstream-key filters survive history folding
- **WHEN** SwissAI request history is filtered by upstream key before and after its usage/report folds run
- **THEN** request counts, model options and key attribution remain unchanged

#### Scenario: SwissAI usage without authoritative pricing
- **WHEN** the operator opens reports containing SwissAI requests
- **THEN** distributions show request counts and omit fabricated dollar costs and account-only thread analytics

### Requirement: Explicit telemetry consent
The fork SHALL retain the dashboard telemetry preview and consent controls. Anonymous telemetry SHALL remain inactive until enabled by an operator's persisted decision or explicit bootstrap environment setting.

#### Scenario: Fresh deployment without a consent decision
- **WHEN** a fresh SwissAI instance starts with no telemetry override
- **THEN** the preview and consent controls are available but no telemetry is transmitted

### Requirement: Evidence before stable release
A stable release SHALL require fake-upstream fault and lifecycle tests, dashboard browser verification, single-node container and migration checks, backup/restore, secret/dependency scans and an authorized live canary. Local lint or build success alone SHALL NOT be called production certification. Optional cluster, alternate-image and external-database checks SHALL NOT be prerequisites for the default laptop/VPS deployment.

#### Scenario: Local tests pass without a live canary
- **WHEN** local tests pass but production deployment or authorized live checks have not run
- **THEN** release status remains a development beta with the missing evidence recorded

#### Scenario: Optional deployment tooling is absent
- **WHEN** the supported single-node release checks run without Rust, Helm, kind or an external PostgreSQL service
- **THEN** those absent optional tools do not block the default laptop/VPS checks

### Requirement: Simple single-node operation
The default deployment SHALL run one application process serving inference and the built dashboard with persistent SQLite storage. It SHALL NOT require Rust, a native transport worker, PostgreSQL, Kubernetes, Nix, or a separate frontend server. Docker SHALL remain optional packaging of the same application.

#### Scenario: Start on a laptop
- **WHEN** an operator installs the Python dependencies, builds the dashboard and starts the documented local command
- **THEN** one application serves the dashboard and SwissAI HTTP routes without a Rust installation or external database

#### Scenario: Default Compose on a VPS
- **WHEN** an operator starts default Compose without a local environment file
- **THEN** only the application starts, its data persists in a named volume, and its published HTTP port binds to loopback for use behind a TLS reverse proxy or SSH tunnel

#### Scenario: Development and optional infrastructure
- **WHEN** the operator runs the default development checks
- **THEN** no Cargo, Rust worker or local Kubernetes cluster is required; frontend development and PostgreSQL remain explicit opt-ins

### Requirement: Non-generating inference-key probes
Key add, replacement and manual probes SHALL check inference-key authentication rather than account-profile login. The check SHALL use an intentionally unroutable model identity and empty messages. Public model listings SHALL NOT be treated as authentication proof. No valid model SHALL be selected for a probe.

#### Scenario: Research key cannot access account profile
- **WHEN** an inference key receives a profile access-token rejection but the inference gateway returns the known sentinel-model rejection
- **THEN** the key is eligible and is not marked invalid because of profile authentication

### Requirement: Conservative probe health changes
Only the recognized sentinel-model rejection SHALL count as authenticated and only an inference 401 SHALL invalidate a key during probing. Other status/body combinations and network failures SHALL be reported as inconclusive without changing existing health. A recognized successful re-probe SHALL clear stale invalidity only for the credential generation that was checked.

#### Scenario: Recover a falsely invalid key
- **WHEN** an explicit probe of a saved invalid key receives the recognized authenticated rejection
- **THEN** its existing identity and secret generation are preserved and its invalid state is cleared

#### Scenario: Unrecognized probe response
- **WHEN** a probe receives a generic 404, an unexpected success, a server failure or an unreachable-provider error
- **THEN** no health state is changed and the result does not claim authentication succeeded
