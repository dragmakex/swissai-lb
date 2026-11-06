# SwissAI fork adaptation

## Decision

Preserve pinned upstream source and Git history. Keep upstream React components and control-plane contracts; do not ship the previous standalone `swissai_lb` prototype. The old prototype was preserved outside the worktree before restoration.

The operator explicitly permits anonymous private-LAN inference when selected. The existing dashboard's client-key toggle overrides that permission. Dashboard login and inference authentication are independent.

## State and ownership

A SwissAI credential is an upstream `ModelSource` with its existing encrypted secret, name and client-key assignment identity. A one-to-one `SwissAIKeyState` stores SwissAI-only fingerprint, redacted prefix, generation and health facts. This avoids duplicating the upstream encryption, client assignment and report identity systems.

The SQL admission transaction locks key-state rows in stable order, counts live leases and inserts one capacity lease before dispatch. PostgreSQL replicas share these rows. SQLite retains the upstream process fence and writer section. Expiring leases renew during a request; losing renewal cancels the owner. Secret generations prevent old health results or continuation IDs from applying to replacements.

One ASGI response owns each logical request. It owns attempt cleanup, downstream visibility, client disconnect monitoring, local usage settlement and the final upstream request-log projection. Stream data is prefetched before sending response headers. Cleanup defers cancellation only long enough to release owned resources, then preserves cancellation instead of retrying.

## Reused infrastructure

- Alembic graph, startup schema checks, database engines and background-session teardown.
- Dashboard users, roles, TOTP, CSRF, permission and audit controls.
- Local API-key hashing, reservations, settlement, assignments and usage windows.
- Request-log and report repositories and UI components.
- Managed HTTP-client generations: rotation retires a generation without closing active transport leases.
- Ingress size/decompression limits, proxy trust, bulkheads and shutdown drain.
- Data retention and multi-replica cache invalidation.

Only the SwissAI inference router is installed. Generic source mutation and subscription/OAuth/file/image/audio/WebSocket routes are not installed. Historical provider-specific source remains until replacement coverage justifies deleting it; there are not two active generation paths.

## Example

A Responses POST selects key A, takes a persisted lease, and receives 429 before output. The attempt is finalized, A receives a persisted cooldown and its lease is released. B receives the same byte body under the original deadline. Only B's response is committed. The local client-key reservation settles once, while two attempt facts remain available to operators.

A timeout can mean A executed the request. The UI and operations notes warn about at-least-once execution. After any downstream commitment, B is not attempted.

## Constraints and release evidence

No real SwissAI key is used in automated tests. Fixtures and fake HTTP servers verify the retry matrix and metadata paths. Real SwissAI error/profile/continuation behavior remains a live-canary gate. Production support also requires real container, PostgreSQL multi-process, restore and load evidence. The tasks file and verification notes must distinguish observed passing suites from historical ChatGPT expectations that require porting.
