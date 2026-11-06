# Implementation / evidence ledger

- [x] Preserve prior prototype outside the worktree and restore pinned upstream source.
- [x] Verify upstream baseline tests before changing provider code.
- [x] Rename runtime/package/bootstrap identifiers; reject upstream production databases.
- [x] Extend upstream model-source key persistence with health, fingerprint and lease facts through a forward migration.
- [x] Add SwissAI management API using upstream dashboard auth, permission and audit contracts.
- [x] Adapt upstream React layout, keys page, client assignments, settings, overview and reports.
- [x] Replace registered proxy surface with transparent SwissAI JSON/SSE routing.
- [x] Prove immutable body, bounded retries/deadline, no post-output retries and cancellation-safe leases.
- [x] Reuse upstream client-key limit settlement, logs, model discovery, metrics and retention.
- [x] Test fake HTTP upstream faults, concurrency, restart, hard ownership and auth modes.
- [x] Verify frontend typecheck/tests/build and browser operator workflows.
- [x] Verify Docker and PostgreSQL / multi-replica deployment, migration and restore.
- [ ] Live authorized canary and secret/dependency/container scans before stable release.

Observed commands, test scope and remaining gates are recorded in [verification.md](verification.md).

Do not check a task without observed evidence. Legacy ChatGPT-only tests remain historical regression context, not a SwissAI compatibility claim.
