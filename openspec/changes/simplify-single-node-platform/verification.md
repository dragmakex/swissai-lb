# Simplification verification

This cleanup is complete for the supported laptop/VPS default. It is not a stable-release or real-provider certification; the original SwissAI release gate remains open.

## Structural review and changes

The thermo-nuclear maintainability review identified an unused second transport implementation as the main removable layer. The Rust workspace, toolchain/lock/audit configuration, native worker/IPC adapter, benchmarks, native dispatch/decoding/error branches and Rust CI area/job are removed, not replaced by stubs or another plugin mechanism. `CodexClient` shrank from 996 to 659 lines. Python error provenance, TLS verification, response cleanup and cancellation behavior remain in the existing client code.

Worker-only tests were retired together with their implementation. Shared Python compact/SSE/stream/WebSocket-routing golden fixtures and assertions were retained under `tests/fixtures/protocol` and `test_python_*_fixtures.py`. Python connector/routing/TLS/cleanup tests remain; native-boundary hint checks now observe the Python connector. Renaming golden tests exposed ambient request-ID leakage from other tests; those fixtures now explicitly scope and restore their request-ID context instead of depending on collection order.

Default Compose now starts only `server`, serves the baked React UI, needs no env file and persists SQLite/encryption state in the unchanged `swissai-lb-data` volume. Its published port is loopback-only; Vite and PostgreSQL require explicit profiles. The redundant command override and retired OAuth callback port are removed. The existing Docker entrypoint remains the only launcher.

Unused shadcn/react-doctor generator/inspection CLIs and scripts were removed; committed UI components and ESLint/type/test gates remain. The removed CLI package's CSS import supplied no utility classes used by this app, so that unused import was removed rather than vendoring hundreds of lines of unused CSS. Bun/Nix lock inputs were regenerated. Frontend tests/build and browser access/layout checks passed afterward.

Ordinary Make checks no longer require Rust, a local cluster or an external database. Frontend checks use two workers to bound laptop memory. Explicit advanced targets remain under `ci-extended`; Helm/Nix cloud jobs require manual workflow dispatch. No security/validation layer, persistence migration or operator volume was removed.

## Passing evidence

| Check | Observed result |
| --- | --- |
| Full retained Python unit suite | **10,435 passed, 4 existing skips**, 21 warnings; `/tmp/swissai-unit-simplified.log`. The smaller count than the preceding 10,561-test checkpoint reflects retiring worker-only assertions, not a filtered passing selection. |
| Actual `make test-unit` selection | **10,492 passed, 6 skipped, 1 existing xfailed**, 21 warnings; `/tmp/swissai-simple-make-unit.log`. Includes unit, simulation and request-log option tests. The expected failure is an inherited legacy bridge's redundant CAS-protected settlement write, not a new SwissAI failure. |
| Actual `make frontend-test` | **1,624 passed in 189 files** with coverage; `/tmp/swissai-simple-frontend-coverage.log`. Statements 83.58%, branches 76.55%, functions 79.50%, lines 83.94%; thresholds were not weakened. |
| Frontend frozen install / types / lint / build | Passed; current lock excludes the retired CLIs and static dashboard is built. |
| Provider/control-plane PostgreSQL selection | **147 passed**; `/tmp/swissai-pg-simplified.log`. Optional PostgreSQL was tested, not made necessary for the default. |
| Actual runtime + SQLite live backup/restore | **1 passed**; `/tmp/swissai-container-simplified-e2e.log`. Includes client auth, generation through the fake provider, durable logs and actual metrics. |
| Actual default Compose | **1 passed**; `/tmp/swissai-compose-e2e.log`. `tests/e2e/test_swissai_compose.py` uses a fresh directory with no env file; only `server` runs; bootstrap/password and encrypted key inventory survive stop/start with the same isolated volume. |
| Built-image browser access/MFA | **6 groups passed**; `/tmp/swissai-verification/access-browser-simplified.log`. Password/MFA login, invalid-code denial, viewer invite/read-only permissions, session revocation, admin MFA recovery/enrollment gating, and password-protected guest at 390x844 with no page overflow. |
| Artifact/deployment/CI/canary regressions | **45 passed**; `/tmp/swissai-simplify-artifacts.log`. These files also pass in the full unit selection. |
| Ruff / architecture / types / diff | `make lint`, `uv run ty check`, `git diff --check` passed; settings remain **96/96**, with a reduced environment-read allowance. |
| Migration graph | Unchanged 265 revisions, single head `20261028_010000_add_swissai_request_metadata`. Base-ref comparison remains unavailable locally; no new migration was introduced. |
| Package | Wheel and sdist built with actual static dashboard; `/tmp/swissai-simplify-package.log`. |
| Specs | Strict cleanup-change, SwissAI change/spec validation passed; all **68 main specs** validate (inherited long-requirement warnings remain). |
| Secrets | Production-source Gitleaks **0 findings across 1,183 files** and all-severity image secret scan **0 findings**. Test fixtures/generated caches are excluded from source scope and do not constitute an all-repository clean claim. |
| Production JavaScript audit | **0 findings**. |

The normal image and current browser/Compose/container evidence use `897631b2d62f4c6de74881a250ef15521554391df41215e74caca4364c5334b1` (`localhost/swissai-lb:verification`). Container tests and browser fixtures use only disposable test credentials; no real SwissAI key or live generation was used. Browser-only containers/volumes and session state were destroyed after checks. Screenshots/results and `/tmp` logs are transient evidence; checked-in tests are the reproducible contracts.

## Still not certified

- **Runtime image gate remains blocked:** 46 HIGH entries across 10 base-OS advisories; zero CRITICAL and no listed fixes. No waiver/baseline exemption.
- **Development audit remains blocked:** one moderate minimatch advisory through ESLint; no HIGH/CRITICAL findings. Do not force a major override merely to silence it.
- No authorized SwissAI canary, real-provider captured contracts, full retained integration/bridge run, third-party-client certification or long load/soak certification. Focused/provider results are not a blanket cloud-CI pass.
- Helm, Nix, distroless, bundled PostgreSQL and multi-replica modes are optional advanced deployment surfaces, not default laptop/VPS release prerequisites. Their historical artifacts were not all revalidated in this cleanup.
- Maintainer branch protection may still name the deleted Rust check; remove that obsolete required check in repository settings before merging. No GitHub settings, publication or production deployment was changed here.
