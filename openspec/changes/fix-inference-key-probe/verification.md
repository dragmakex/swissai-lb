# Probe authentication fix: evidence

## Root cause

The add/replace/probe path called `/v1/profile` and used its account access-token rejection to invalidate a research inference key. Fake upstreams accepted those keys at profile and concealed the authentication-boundary mismatch.

Read-only inspection of the two operator records found stored credentials that decrypt, have the expected prefix and contain no whitespace. Direct requests sent credentials only to the canonical SwissAI HTTPS service; no raw keys were printed or written to artifacts. Both received profile `401 Invalid access token`. At the inference boundary, the invalid control received 401, while each real key received 404 `invalid_request_error` with `Model '__swissai_lb_auth_probe__' not found.` and the fully-namespaced-model guidance. These deliberately unroutable requests supplied empty messages; no successful generation or full inference canary was performed.

Other non-generating diagnostics (empty chat input and tokenize) returned server/unsupported-parser errors; those are not used as validity proof. The public OpenAPI also explicitly documents the profile rotation route as Auth0 access-token authentication, not the research API key. That mutation route was not called.

## Fix

Use the inference boundary with the unnamespaced sentinel/empty messages, recognize only the observed status/type/message combination, preserve health on inconclusive/network/oversized responses, and retain inference-401 invalidation. Correct fake profile authentication and keep probes separate from generation/attempt counters. Successful manual re-probe reuses the generation-fenced health operation to recover stale invalid state without replacing credentials.

## Validation

- **84 passed** across probe policy/API regressions, key-pool product paths, SDK and lifecycle; `/tmp/swissai-auth-probe-regressions.log`.
- API regressions cover profile-inaccessible valid keys on add, genuine inference 401, stale invalid-state recovery with unchanged secret/fingerprint/generation, and inconclusive responses preserving healthy/invalid states.
- New image `6159eb61cbc802477943764fdf635f62437af29b1f712eb27afb7d4aa97339b1`: actual container/client-auth/inference/SQLite backup+restore **1 passed**, against the corrected fake; `/tmp/swissai-probe-container-e2e.log`.
- `make lint`, full Python typecheck, strict fix-change and owning SwissAI spec validation passed.
- Full unit/frontend suites were not rerun for this focused backend fix; earlier whole-suite evidence remains separately scoped.

## Operator recovery

The running non-reloading Python process was not stopped and the operator database/credentials were not edited. Stop and restart it with `uv run swissai-lb --host 127.0.0.1 --port 2456`, then click **Probe** for each saved invalid key. No deletion, credential re-entry or encryption-key replacement is needed. Docker users rebuild/restart their image before probing.

This establishes the inference authentication distinction, not model availability, quota entitlement, a successful real completion or live key-rotation certification.
