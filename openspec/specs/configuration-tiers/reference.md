<!-- GENERATED — edit scripts/generate_settings_reference.py, not this file. -->

# Settings Reference

**GENERATED** — edit `scripts/generate_settings_reference.py`, not this file.
Regenerate with `uv run python scripts/generate_settings_reference.py`;
`tests/unit/test_settings_reference.py` fails when this page drifts from
`app/core/config/settings.py`.

SwissAI LB retains 96 inherited application settings. Every setting is an environment
variable, normally with the `SWISSAI_LB_` prefix (process environment or `.env` /
`.env.local` next to the process); aliased settings list every accepted name.
All defaults work with zero configuration —
start from [SwissAI operations](../swissai-key-pool/context.md) for the supported setup.
Inherited OAuth/bridge settings do not enable retired ChatGPT inference routes.
Treat the remaining reference as advanced operational tunables.

## Tiers

The **Tier** column is the configuration policy for each setting
(`app/core/config/tiers.py`, enforced by `scripts/check_settings_tiers.py`):

- **T0** bootstrap — needed before the database is reachable; env only.
- **T1** instance topology — legitimately differs per replica or deployment; env only.
- **T2** secret — encrypted in the database; env is at most a seed.
- **T3** behaviour tunable / feature flag — the dashboard is the management
  surface. `T3 → dashboard` marks a setting that already has a
  `dashboard_settings` column of the same name: the dashboard value wins and
  the variable is a deprecated fallback. `T3 (env, migrating)` marks the
  remaining env-only backlog.
- **T4** incident debug — env allowed, dashboard toggle recommended.

## `PORT` (special case, no prefix)

The listen port (default `2455`) is read from the bare `PORT` process
environment variable, not a `SWISSAI_LB_*` setting, and applies to host
(uvx/local) runs only — env files map only prefixed variables. In Docker the
container always listens on 2455 (the entrypoint pins `--port 2455`); change
the host side of the compose `ports` mapping instead.

## `SWISSAI_LB_ENV_FILE` (special case, bootstrap only)

`.env` / `.env.local` are discovered next to the installed module root (the
repository checkout). `SWISSAI_LB_ENV_FILE` — an `os.pathsep`-separated list
of paths — overrides that discovery for installs whose module root cannot
contain env files. It must be set in the process environment, not in an env file:
the env-file locations have to be known before env files are read.

## `SWISSAI_LB_WORKERS_PER_INSTANCE` (special case, startup guard)

Not a setting: the only supported value is `1` (one worker process per
instance), so there is nothing to configure. If it is set to anything else,
startup fails with a settings validation error. The supported default is one
application process using SQLite; optional PostgreSQL coordination does not
make multiple workers within one instance supported.

## Process-level environment variables (not settings)

These are third-party or POSIX conventions the retained application honors without
making them settings. They are read by their owning launcher, library, or
frozen migration rather than through `Settings`. Together with `Settings`
itself this table is the allowlist of environment reads under `app/`;
anything else belongs in `app/core/config/settings.py`.

| Environment variable(s) | Consumer |
| --- | --- |
| `HOST`, `PORT`, `SSL_CERTFILE`, `SSL_KEYFILE`, `UVICORN_TIMEOUT_KEEP_ALIVE`, `UVICORN_WS_MAX_SIZE` | Uvicorn launch defaults read once by the `swissai-lb` CLI (`app/cli.py`); host runs only. |
| `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `WS_PROXY`, `NO_PROXY` (and lowercase) | Outbound proxy conventions honored by httpx/aiohttp/websockets for upstream egress. |
| `REQUEST_METHOD` | CGI marker; when present `HTTP_PROXY` is ignored (httpoxy guard, mirrors the httpx/requests rule). |
| `TZ` | POSIX process timezone; automation schedules with the `server_default` timezone resolve to it (falling back to the host local zone, then UTC). |
| `PROMETHEUS_MULTIPROC_DIR` | prometheus_client multiprocess-mode convention. |
| `GITHUB_TOKEN` | Optional bearer token for the GitHub latest-release version check. |
| `POD_IP`, `POD_NAME`, `HOSTNAME`, `KUBERNETES_SERVICE_HOST` | Kubernetes/pod identity used for multi-replica validation and deployment-kind telemetry. |
| `CODEX_HOME`, `USERPROFILE`, `WSL_DISTRO_NAME` | Codex CLI home discovery for the retained `swissai-lb codex-sessions retag` compatibility tool. |
| `SWISSAI_LB_TEST_DATABASE_URL` | Test-suite/CI only: overrides the database used by the test session factory. |
| `SWISSAI_LB_ADDITIONAL_QUOTA_REGISTRY_FILE` (inside `app/db/alembic/versions/**` only) | Frozen Alembic migrations read the process environment directly because migrations must not depend on `Settings`; the live setting of the same name is documented in the tables below. |

## Core

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_DATA_DIR` | T0 | `Path` | `~/.swissai-lb` (host) / `/var/lib/swissai-lb` (container) |

## Database

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_DATABASE_ALEMBIC_AUTO_REMAP_ENABLED` | T0 | `bool` | `True` |
| `SWISSAI_LB_DATABASE_MAX_OVERFLOW` | T1 | `int` | `15` |
| `SWISSAI_LB_DATABASE_MIGRATE_ON_STARTUP` | T0 | `bool` | `True` |
| `SWISSAI_LB_DATABASE_MIGRATION_LOCK_TIMEOUT_SECONDS` | T0 | `float` | `300.0` |
| `SWISSAI_LB_DATABASE_MIGRATIONS_FAIL_FAST` | T0 | `bool` | `True` |
| `SWISSAI_LB_DATABASE_POOL_SIZE` | T1 | `int` | `25` |
| `SWISSAI_LB_DATABASE_SQLITE_PRE_MIGRATE_BACKUP_ENABLED` | T0 | `bool` | `True` |
| `SWISSAI_LB_DATABASE_SQLITE_PRE_MIGRATE_BACKUP_MAX_FILES` | T0 | `int` | `5` |
| `SWISSAI_LB_DATABASE_SQLITE_STARTUP_CHECK_MODE` | T0 | `'quick' \| 'full' \| 'off'` | `'quick'` |
| `SWISSAI_LB_DATABASE_URL` | T0 | `str` | `sqlite+aiosqlite:///<data_dir>/store.db` |

## Encryption

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_ENCRYPTION_KEY_FILE` | T0 | `Path` | `<data_dir>/encryption.key` |
| `SWISSAI_LB_ENCRYPTION_KEY_FINGERPRINT_MODE` | T0 | `'enforce' \| 'warn' \| 'off'` | `'enforce'` |

## Upstream transport

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_UPSTREAM_BASE_URL` | T1 | `str` | `'https://api.swissai.svc.cscs.ch/v1'` |
| `SWISSAI_LB_UPSTREAM_CONNECT_TIMEOUT_SECONDS` | T3 (dashboard) | `float` | `8.0` |
| `SWISSAI_LB_UPSTREAM_ROUTE_CACHE_TTL_SECONDS` | T1 | `float` | `60.0` |
| `SWISSAI_LB_UPSTREAM_WEBSOCKET_TRUST_ENV` | T1 | `bool` | auto-detected from outbound proxy env vars |

## HTTP & streaming

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_COMPACT_REQUEST_BUDGET_SECONDS` | T3 (dashboard) | `float` | `180.0` |
| `SWISSAI_LB_HTTP_CONNECTOR_LIMIT` | T1 | `int` | `100` |
| `SWISSAI_LB_HTTP_CONNECTOR_LIMIT_PER_HOST` | T1 | `int` | `50` |
| `SWISSAI_LB_HTTP_RESPONSES_STREAM_REQUEST_BUDGET_SECONDS` | T3 (dashboard) | `float` | `7200.0` |
| `SWISSAI_LB_SSE_KEEPALIVE_INTERVAL_SECONDS` | T3 (dashboard) | `float` | `10.0` |
| `SWISSAI_LB_STREAM_IDLE_TIMEOUT_SECONDS` | T3 (dashboard) | `float` | `300.0` |
| `SWISSAI_LB_TRANSCRIPTION_REQUEST_BUDGET_SECONDS` | T3 (dashboard) | `float` | `120.0` |

## HTTP Responses session bridge

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_ADVERTISE_BASE_URL` | T1 | `str \| None` | `None` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_CODEX_PREWARM_ENABLED` | T3 (dashboard) | `bool` | `False` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_ENABLED` | T4 | `bool` | `False` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_INSTANCE_ID` | T1 | `str` | process hostname |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_INSTANCE_RING` | T1 | `list[str]` | `[]` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_MAX_SESSIONS` | T1 | `int` | `256` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_EVENT_SPOOL_BATCH_SIZE` | T1 | `int` | `32` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_EVENT_SPOOL_FLUSH_INTERVAL_SECONDS` | T1 | `float` | `0.1` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_EVENT_SPOOL_MAX_PENDING_BYTES` | T1 | `int` | `33554432` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_EVENT_SPOOL_MAX_PENDING_EVENTS` | T1 | `int` | `2048` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_SPOOL_RETENTION_SECONDS` | T3 (dashboard) | `float` | `604800` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_QUEUE_LIMIT` | T1 | `int` | `8` |
| `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_REQUEST_BUDGET_SECONDS` | T3 (dashboard) | `float` | `7200.0` |

## Proxy admission & account caps

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_PROXY_ACCOUNT_CAP_PARTITION_SCALE_DOWN_SECONDS` | T1 | `int` | `60` |
| `SWISSAI_LB_PROXY_ACCOUNT_CAPS_SCOPE` | T1 | `'partitioned' \| 'replica'` | `'partitioned'` |
| `SWISSAI_LB_PROXY_ACCOUNT_ERROR_RATE_WEIGHTING_ENABLED` | T3 (dashboard) | `bool` | `True` |
| `SWISSAI_LB_PROXY_ACCOUNT_INFLIGHT_PENALTY_PCT` | T3 (dashboard) | `float` | `2.5` |
| `SWISSAI_LB_PROXY_ACCOUNT_LEASE_TOKEN_WEIGHT` | T3 (dashboard) | `float` | `1.0` |
| `SWISSAI_LB_PROXY_ACCOUNT_LEASE_TTL_SECONDS` | T3 (dashboard) | `float` | `900.0` |
| `SWISSAI_LB_PROXY_ACCOUNT_RESPONSE_CREATE_LIMIT` | T3 (dashboard) | `int` | `4` |
| `SWISSAI_LB_PROXY_ACCOUNT_STREAM_LIMIT` | T3 (dashboard) | `int` | `8` |
| `SWISSAI_LB_PROXY_ACCOUNT_STREAM_RECOVERY_RESERVE` | T3 (dashboard) | `int` | `1` |
| `SWISSAI_LB_PROXY_ALLOW_ANONYMOUS_LAN` | T1 | `bool` | `False` |
| `SWISSAI_LB_PROXY_API_KEY_FAIR_SHARE_CONGESTION_THRESHOLD_PCT` | T3 (dashboard) | `int` | `0` |
| `SWISSAI_LB_PROXY_DOWNSTREAM_WEBSOCKET_IDLE_TIMEOUT_SECONDS` | T3 (dashboard) | `float` | `120.0` |
| `SWISSAI_LB_PROXY_OVERLOAD_ISOLATION_SECONDS` | T3 (dashboard) | `int` | `1800` |
| `SWISSAI_LB_PROXY_REQUEST_BUDGET_SECONDS` | T3 (dashboard) | `float` | `600.0` |
| `SWISSAI_LB_PROXY_RESPONSE_CREATE_LIMIT` | T1 | `int` | `256` |
| `SWISSAI_LB_PROXY_UNAUTHENTICATED_CLIENT_CIDRS` | T1 | `list[str]` | `[]` |

## OAuth

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_OAUTH_CALLBACK_HOST` | T1 | `str` | `127.0.0.1` (host) / `0.0.0.0` (container) |

## Token refresh

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_AUTH_GUARDIAN_ENABLED` | T3 (dashboard) | `bool` | `True` |

## Usage

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_ADDITIONAL_QUOTA_REGISTRY_FILE` | T1 | `Path \| None` | `None` |
| `SWISSAI_LB_RATE_LIMIT_RESET_CREDITS_REFRESH_ENABLED` | T3 (dashboard) | `bool` | `True` |

## Model registry

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_MODEL_CONTEXT_WINDOW_OVERRIDES` | T3 (dashboard) | `dict[str, int]` | `{}` |
| `SWISSAI_LB_MODEL_REGISTRY_CLIENT_VERSION` | T1 | `str` | `'0.163.0'` |
| `SWISSAI_LB_MODEL_REGISTRY_SNAPSHOT_MAX_AGE_SECONDS` | T1 | `int` | `86400` |

## Firewall

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_FIREWALL_IP_CACHE_TTL_SECONDS` | T1 | `int` | `30` |
| `SWISSAI_LB_FIREWALL_TRUST_PROXY_HEADERS` | T1 | `bool` | `False` |
| `SWISSAI_LB_FIREWALL_TRUSTED_PROXY_CIDRS` | T1 | `list[str]` | `['127.0.0.1/32', '::1/128']` |
| `FORWARDED_ALLOW_IPS` (alias `SWISSAI_LB_FORWARDED_ALLOW_IPS`) | T1 | `str \| None` | `None` |

## Dashboard

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_CONNECT_ADDRESS` | T1 | `str \| None` | `None` |
| `SWISSAI_LB_DASHBOARD_AUTH_MODE` | T1 | `'standard' \| 'trusted_header' \| 'disabled'` | `'standard'` |
| `SWISSAI_LB_DASHBOARD_AUTH_PROXY_GROUPS_HEADER` | T1 | `str` | `'Remote-Groups'` |
| `SWISSAI_LB_DASHBOARD_AUTH_PROXY_HEADER` | T1 | `str` | `'Remote-User'` |
| `SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN` | T0 | `str \| None` | `None` |
| `SWISSAI_LB_DASHBOARD_TRUST_LOOPBACK_HOST_HEADER_FOR_LONG_SESSIONS` | T1 | `bool` | `False` |

## Conversation archive

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_CONVERSATION_ARCHIVE_DIR` | T1 | `Path` | `<data_dir>/conversation-archive` |
| `SWISSAI_LB_CONVERSATION_ARCHIVE_ENABLED` | T3 (dashboard) | `bool` | `False` |
| `SWISSAI_LB_CONVERSATION_ARCHIVE_QUEUE_MAX_BYTES` | T1 | `int` | `268435456` |

## Schedulers

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_AUTOMATIONS_SCHEDULER_ENABLED` | T3 (dashboard) | `bool` | `True` |

## Multi-replica

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_LEADER_ELECTION_ENABLED` | T1 | `bool` | `True` |
| `SWISSAI_LB_LEADER_ELECTION_TTL_SECONDS` | T1 | `int` | `60` |

## Observability

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_LOG_FORMAT` | T1 | `'text' \| 'json'` | `'text'` |
| `SWISSAI_LB_METRICS_ENABLED` | T1 | `bool` | `False` |
| `SWISSAI_LB_METRICS_PORT` | T1 | `int` | `9090` |
| `SWISSAI_LB_OTEL_ENABLED` | T1 | `bool` | `False` |
| `SWISSAI_LB_OTEL_EXPORTER_ENDPOINT` | T1 | `str` | `''` |
| `SWISSAI_LB_TRACE` | T4 | `str` | `''` |

## Resilience & load shedding

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_BACKPRESSURE_MAX_CONCURRENT_REQUESTS` | T1 | `int` | `0` |
| `SWISSAI_LB_BULKHEAD_DASHBOARD_LIMIT` | T1 | `int` | `50` |
| `SWISSAI_LB_BULKHEAD_PROXY_LIMIT` | T1 | `int` | `512` |
| `SWISSAI_LB_CIRCUIT_BREAKER_ENABLED` | T3 (dashboard) | `bool` | `False` |
| `SWISSAI_LB_DETERMINISTIC_FAILOVER_ENABLED` | T3 (dashboard) | `bool` | `True` |
| `SWISSAI_LB_MEMORY_REJECT_THRESHOLD_MB` | T1 | `int` | `0` |
| `SWISSAI_LB_SHUTDOWN_DRAIN_TIMEOUT_SECONDS` | T1 | `int` | `30` |
| `SWISSAI_LB_SOFT_DRAIN_ENABLED` | T3 (dashboard) | `bool` | `True` |

## Other

| Environment variable | Tier | Type | Default |
| --- | --- | --- | --- |
| `SWISSAI_LB_ALLOW_INSECURE_UPSTREAM` | T1 | `bool` | `False` |
| `SWISSAI_LB_EVENT_LOOP_LAG_WARN_THRESHOLD_SECONDS` | T1 | `float` | `0.5` |
| `SWISSAI_LB_TELEMETRY_ENABLED` | T3 (dashboard) | `bool \| None` | `None` |
| `SWISSAI_LB_TELEMETRY_ENDPOINT` | T1 | `str` | `'https://telemetry.tokmaxxing.com'` |
| `SWISSAI_LB_THREAD_CACHE_IDENTITY_MODE` | T3 (dashboard) | `str` | `'shared'` |
| `SWISSAI_LB_TIMEOUT_INVARIANT_VALIDATION_STRICT` | T4 | `bool` | `False` |

## Removed

Removed settings (ignored with a one-release startup warning; each is now a
fixed default or a dashboard runtime setting — see [configuration policy](spec.md)):

- `SWISSAI_LB_REQUEST_LOG_RETENTION_DAYS`
- `SWISSAI_LB_USAGE_HISTORY_RETENTION_DAYS`
- `SWISSAI_LB_HTTP_DOWNSTREAM_TRANSPORT_POLICY`
- `SWISSAI_LB_OPENAI_CACHE_AFFINITY_MAX_AGE_SECONDS`
- `SWISSAI_LB_WARMUP_MODEL`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_GATEWAY_SAFE_MODE`
- `SWISSAI_LB_UPSTREAM_STREAM_TRANSPORT`
- `SWISSAI_LB_UPSTREAM_COMPACT_TIMEOUT_SECONDS`
- `SWISSAI_LB_MAX_SSE_EVENT_BYTES`
- `SWISSAI_LB_UPSTREAM_RESPONSE_CREATE_MAX_BYTES`
- `SWISSAI_LB_OAUTH_TIMEOUT_SECONDS`
- `SWISSAI_LB_TOKEN_REFRESH_TIMEOUT_SECONDS`
- `SWISSAI_LB_TOKEN_REFRESH_CLAIM_TTL_SECONDS`
- `SWISSAI_LB_PROXY_REFRESH_FAILURE_COOLDOWN_SECONDS`
- `SWISSAI_LB_PROXY_ADMISSION_WAIT_TIMEOUT_SECONDS`
- `SWISSAI_LB_USAGE_FETCH_TIMEOUT_SECONDS`
- `SWISSAI_LB_USAGE_FETCH_MAX_RETRIES`
- `SWISSAI_LB_USAGE_REFRESH_ENABLED`
- `SWISSAI_LB_USAGE_REFRESH_INTERVAL_SECONDS`
- `SWISSAI_LB_USAGE_REFRESH_AUTH_FAILURE_COOLDOWN_SECONDS`
- `SWISSAI_LB_LIVE_USAGE_INGESTION_ENABLED`
- `SWISSAI_LB_RATE_LIMIT_RESET_CREDITS_REFRESH_INTERVAL_SECONDS`
- `SWISSAI_LB_STICKY_SESSION_CLEANUP_ENABLED`
- `SWISSAI_LB_QUOTA_PLANNER_SCHEDULER_ENABLED`
- `SWISSAI_LB_MODEL_REGISTRY_ENABLED`
- `SWISSAI_LB_MAX_DECOMPRESSED_BODY_BYTES`
- `SWISSAI_LB_MAX_DECOMPRESSED_RESPONSES_BODY_BYTES`
- `SWISSAI_LB_IMAGE_INLINE_FETCH_ENABLED`
- `SWISSAI_LB_IMAGE_INLINE_ALLOWED_HOSTS`
- `SWISSAI_LB_IMAGES_DEFAULT_MODEL`
- `SWISSAI_LB_OPENAI_PROMPT_CACHE_KEY_DERIVATION_ENABLED`
- `SWISSAI_LB_PROXY_TOKEN_REFRESH_LIMIT`
- `SWISSAI_LB_PROXY_UPSTREAM_WEBSOCKET_CONNECT_LIMIT`
- `SWISSAI_LB_PROXY_COMPACT_RESPONSE_CREATE_LIMIT`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_IDLE_TTL_SECONDS`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_CODEX_IDLE_TTL_SECONDS`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_STUCK_GATE_RETIRE_AFTER_SECONDS`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_ANCHOR_POISON_FAILURE_THRESHOLD`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_SERVER_RECOVERY_MAX_ATTEMPTS`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_CLEAN_CLOSE_RETRY_JITTER_MAX_SECONDS`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_LEDGER_ENABLED`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_AMBIGUOUS_CONTINUATION_RECOVERY_MODE`
- `SWISSAI_LB_TOKEN_REFRESH_INTERVAL_DAYS`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_EVENT_SPOOL_MAX_BYTES`
- `SWISSAI_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_SPOOL_FORMAT`

---

*Owner: [configuration-tiers](spec.md). See also [user-documentation](../user-documentation/spec.md) and [SwissAI key pool](../swissai-key-pool/spec.md).*
