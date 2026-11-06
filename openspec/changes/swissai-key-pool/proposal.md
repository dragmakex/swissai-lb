# SwissAI key pool

Adapt pinned codex-lb 72630bbfeee9e3b0d9acfb95e2b1e706b8b0188e rather than replacing its dashboard and control plane. The [initial brief](original-brief.md) records planning provenance; the owning SwissAI requirements and subsequent change deltas define the current acceptance contract. Preserve dashboard auth, roles, audit, client-key limits/assignments, reports, request logs, migrations, middleware, and packaging. Replace subscription/OAuth generation routing with one SwissAI bearer-key pool. Do not register unsupported provider endpoints.

The operator explicitly permits LAN-wide anonymous inference when client-key authentication is off. When on, every inference route requires a valid local client key. Dashboard authentication remains separate.

## Capabilities

### New capabilities
- `swissai-key-pool`: SwissAI-only bearer-key management, pooled admission, failover, continuation ownership, dashboard adaptation and release evidence.

### Modified capabilities
- None in this initial provider delta. Retained upstream capabilities remain the baseline; any separate contract changes require focused deltas.

## Impact

The inference router and provider background jobs are replaced. The upstream control plane, React shell, storage, transport leases and client-key settlement remain in use. Fresh fork databases are required; existing codex-lb production databases are not migrated in place.
