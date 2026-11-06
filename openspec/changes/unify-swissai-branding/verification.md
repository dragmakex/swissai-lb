# Branding verification

## Result

SwissAI LB is the active dashboard, CLI and operator-guide identity. README retains exactly one short upstream-attribution line. Project/release links use `dragmakex/swissai-lb`; telemetry help targets the current operations guide. LICENSE, Git history, protocol identifiers, stable IDs, legacy provider tags and telemetry consent/destinations are preserved.

## Evidence

Local logs and disposable UI screenshots: `/tmp/swissai-branding/`.

- Full retained `make test-unit` checkpoint: **10,316 passed, 6 skipped, 1 existing xfailed, 21 warnings**. A later additional document guard and CLI string-formatting correction were covered by the final targeted run: **42 passed**.
- Frontend lint/types/build and all tests: **1,624 passed / 189 files**.
- Desktop **1440×1000** and mobile **390×844** Chromium before/after checks: footer label/destination verified; after pages contain no inherited product brand and have no horizontal overflow. Screenshots use only synthetic API fixtures, not operator data. Temporary static servers and browser contexts were closed.
- Backend targeted selection: **210 passed, 1 failed**. The failure is the legacy account-probe HTTP 405 described below; runtime-version, recovery, branding and consent checks passed.
- Final Ruff/format/Ty and `make lint`/`make typecheck`: pass. Settings budget remains **96/96**; migration head/count unchanged.
- `uv lock --check`: pass; no dependency changes.
- Production-source secret scan: **0 findings / 1,118 files**.
- Strict branding change validation: pass. Default canonical validation: **68 passed**; this is not a global strict-spec claim.
- README attribution/current-guide/frontend branding guards and `git diff --check`: pass.

## Baseline failure and limits

`tests/integration/test_fleet_summary_api.py::test_force_probe_advances_usage_freshness_without_changing_oauth_refresh` expects a retired account-probe endpoint to return 200; the active application returns 405. An isolated archive of pre-branding commit `1cf8c2f0` reproduces the same failure with its original Python/test files. The test was neither deleted nor skipped, and the retired route was not restored to make it pass. Evidence: `baseline-fleet.log` and `backend-tests.log`.

No container/image, PostgreSQL matrix, live-provider, soak or cloud CI certification was performed. Migration base-ref comparison remains unavailable. Existing broader release/security limits remain open. No operator database, credential, server process, Git history or remote publication was changed by the branding implementation. Generated frontend assets were rebuilt; the existing server processes were not restarted.

Historical change records and legacy engineering contracts retain their original terminology where it is compatibility/provenance data rather than current product branding.
