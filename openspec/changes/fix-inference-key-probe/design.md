# Design

## Context

The old probe sent a research key to `/v1/profile` and interpreted its 401 as an invalid inference key. Read-only local inspection confirmed both saved credentials decrypt and contain no whitespace. Live diagnostics observed profile 401 for both; the same deliberately invalid inference request returned 401 for an invalid control key and 404 `invalid_request_error` with the exact sentinel-model-not-found message for each real key. No successful completion/generation was requested.

## Decisions

Use `POST /chat/completions` with model `__swissai_lb_auth_probe__` and empty messages. The sentinel is intentionally not fully namespaced, so it cannot route to the provider's required `<namespace>/<organization>/<model>` identity. Match status 404, error type and sentinel-specific message together. Generic 404/400/500, malformed payloads and network errors do not prove validity and do not change health. Inference 401 uses the existing invalidation rule. Never use a public models 200 as proof of authentication.

Reuse bounded response reads, encrypted secret access, managed HTTP sessions and generation-fenced `health(..., probe=True)`. Successful auth checks clear stale invalid/cooldown state through that existing operation. No automatic SQL repair or migration, no forced process restart and no live generation canary.

## Risks / Trade-offs

- Provider rejection format can change → report inconclusive, not valid/invalid, and preserve existing state.
- Provider no longer enforces namespace → empty messages still provide no generation input; unexpected success is inconclusive, not silently accepted.
- Old saved invalid keys remain blocked until re-probed → operator restarts the non-reloading app and clicks Probe; no key re-entry is needed.
