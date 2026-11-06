# Design

## Context

See proposal.md. SwissAI already forwards using the managed aiohttp model-source session. Rust is an inherited alternative behind other clients, not an optimization used by this provider. The Python package does not depend on a compiled Rust extension.

## Goals / Non-Goals

Goals: remove a transport implementation rather than add a feature flag; preserve the tested Python paths; make the default operator and development path one-node and unsurprising.

Non-goals: rewrite the React dashboard, replace the persistence layer, weaken authentication/TLS/secret handling, delete migration history, claim a live-provider pass, or rewrite every dormant ChatGPT subsystem in this change.

## Decisions

- Delete the worker/workspace/IPC adapter and remove native dispatch, framing and error branches at their callers. Do not retain a stub that silently returns `None`, a compatibility plugin registry or a second renamed worker.
- Preserve Python connect/body failure provenance, cancellation and response/session cleanup. Keep Python golden/protocol assertions where native tests also verified a shared contract. Retire only worker-specific IPC/execution assertions and record their removal explicitly.
- Keep the single-process Python launcher and baked static dashboard. Compose defaults to only `server`, loopback HTTP, an optional env file and the existing named data volume. Put Vite behind a `dev` profile; keep PostgreSQL opt-in for existing operators without connecting or migrating it implicitly.
- Keep useful Docker packaging and basic Make shortcuts. Make ordinary CI independent of Rust and local cluster/database services; advanced deployment checks remain separate explicit targets.
- Remove shadcn/react-doctor CLIs from local development dependencies. Their generated UI is already committed; neither CLI is a runtime feature or an existing mandatory lint/test gate. Retain the established lint/type/test tooling.

## Risks / Trade-offs

- Legacy native/Python mixed tests can hide real fallback/error coverage → inspect callers and preserve equivalent Python assertions; run the full unit suite and provider integration/product-path tests.
- Loopback Compose binding changes remote access → document a TLS reverse proxy or SSH tunnel; do not publish an unauthenticated service by default.
- Profiles and env-file semantics affect developer commands → test resolved/default Compose services and preserved data volume names.
- Historical OpenSpec/docs describe upstream native capabilities → retain historical artifacts, scope the fork's supported contract in SwissAI requirements/context, and do not assert removed worker support.

## Migration Plan

No schema or data migration. Keep named volumes and encryption keys unchanged. Rebuild the normal image or Python package; remove old worker/toolchain artifacts from source/CI only. Existing explicit advanced deployment artifacts remain available but are not required for laptop/VPS use. Rollback uses the previous image with the same data and encryption key; do not remove volumes to roll back.
