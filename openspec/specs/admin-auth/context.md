# admin-auth Context

## Bootstrap Token

### Purpose

The bootstrap token secures the initial remote password setup flow. Without it, anyone on the network could set the dashboard password on a fresh install. It is a one-time credential — only needed during the first `POST /api/dashboard-auth/password/setup` from a non-local client.

### Behavior

**Auto-generation (default path):**

On server startup, if no dashboard password or manual bootstrap token is configured, the application generates a cryptographically random bootstrap token. The SwissAI fork writes the generated plaintext to `<data_dir>/bootstrap.token` with mode 0600, not server logs. Database-backed encrypted/hash state supports validation and recovery; retain the matching encryption key and data directory.

**Priority chain:**

A manual `SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN` takes precedence over generated state. The session endpoint exposes only whether a bootstrap token is configured; password setup validates the credential without returning it to an unauthenticated caller.

**Lifecycle:**

1. Startup creates or recovers bootstrap state while password setup is pending.
2. The operator reads `bootstrap.token` from the protected data directory (or uses the manual setting) and enters it with the new dashboard password.
3. Password setup validates the token and atomically consumes shared bootstrap state.
4. The consumed credential is no longer a sign-in mechanism. Protect and back up the data directory; do not publish its files.

**Restart behavior:**

Before password setup, startup reuses recoverable bootstrap state rather than invalidating the pending credential. The fork's recovery channel is the protected token file, not logs. Any optional shared-database deployment must also share the encryption key.

### Manual Override

Set `SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN=<value>` as an environment variable before starting. When set:
- Auto-generation is skipped
- No token is logged
- The env var value is used for validation
- The token persists across restarts (it's in the environment)

### Localhost Bypass

Requests from localhost (127.0.0.1, ::1) bypass bootstrap entirely — no token or password needed for initial setup. This is handled by `is_local_request()` in `app/core/request_locality.py` and checked in both the session endpoint and the auth guard.

Behind a trusted proxy, locality comes from the resolved client identity rather than from header presence alone. Chain headers preserve repeated fields because they form one ordered route; singleton identity headers (`X-Real-IP`, `True-Client-IP`, and `CF-Connecting-IP`) must appear once. Repetition is ambiguous and fails closed so a client-preseeded loopback field cannot win a first-value lookup.

For authentication and locality, each allowed identity-header family containing a non-empty value is resolved independently with its existing hardened rules. Redundant families are accepted when they agree: for example, `X-Forwarded-For: 127.0.0.1` and `Forwarded: for=127.0.0.1` establish one loopback identity. If the `Forwarded` value instead resolves to `203.0.113.24`, or if either populated family is malformed, the locality check fails closed instead of choosing one by precedence. Families whose values are all empty or whitespace-only are ignored. Repeated chain fields and singleton duplicates retain their established within-family behavior. Generic client-IP consumers such as the API firewall, request logging, and bridge metadata retain their established resolution behavior. Drain and audit do not participate in this consensus path and remain unchanged.

Owned launchers disable Uvicorn's outer projection so the application can preserve the raw HTTP/WebSocket peer before applying the same proxy projection once. Locality and the disabled-auth socket allowlist use that preserved peer; generic consumers continue to see the projected client and scheme.

Direct loopback requests remain local when proxy-header trust is disabled only if every forwarded client-IP field value is empty. Repeated fields are all inspected: for example, an empty first `X-Forwarded-For` field followed by `203.0.113.24` is treated as proxied and remote. The same shared locality decision protects first-run dashboard setup and unauthenticated protected proxy access.

### Threat Model

- **Token file**: Host/container access can read the bootstrap credential; protect filesystem permissions, backups and volume access. Do not log or commit it.
- **Database state**: The stored credential is encrypted for recovery and separately hashed for validation; setup consumes the shared state.
- **Recovery**: See [host login recovery](ops.md). Do not weaken proxy trust to work around a lockout.

## Session Management

Stateless encrypted cookies using Fernet. Session payload: `{exp, pw, tv}`. Default persisted TTL: 1 year for local dashboard use. Long configured lifetimes above 30 days fall back to 12 hours for non-loopback, proxy-aware, trusted-header, or bridge-without-override requests. Localhost-published bridge deployments can opt in with `SWISSAI_LB_DASHBOARD_TRUST_LOOPBACK_HOST_HEADER_FOR_LONG_SESSIONS=true`, which still requires a loopback dashboard URL and no non-empty forwarded-client field value. Every occurrence is inspected: an empty first `X-Forwarded-For` field cannot hide a later non-empty duplicate. No server-side session storage.

## Rate Limiting

Password login and TOTP verification: max 8 attempts per 60-second window per client IP. Stored in `rate_limit_attempts` table. Returns 429 with `Retry-After` header.

## Audit Logging

Events: `login_success`, `login_failed`, `totp_enabled`, `totp_disabled`, `settings_changed`. Stored in `audit_logs` table via `AuditService.log_async()`.
