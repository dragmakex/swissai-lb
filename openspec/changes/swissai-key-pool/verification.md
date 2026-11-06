# Verification evidence and remaining release gates

This is a development beta, not production certification. The [initial brief](original-brief.md) is preserved planning input; the acceptance contract is the [SwissAI requirements](../../specs/swissai-key-pool/spec.md) with active change deltas, including the explicitly reduced delivery scope. Checked tasks describe observed implementation evidence, not blanket compatibility with every historical codex-lb test.

## Scope and decisions

The pinned upstream fork and its React control plane remain in place. This verification pass concentrated on real server processes, PostgreSQL admission, SDK compatibility, storage safety and browser operator workflows. All credentials used here were disposable test credentials; no authorized SwissAI generation was performed.

The local fake upstream is `tests/fixtures/fake_swissai.py`. It binds to loopback when launched as a module, accepts only fake `sk-rc-test-...` credentials, and implements deterministic SDK contract responses. Its profile/error/continuation behavior is a fixture, not evidence about the real provider.

## Observed passing checks

Key-pool implementation: **12/13 tasks checked**. React/control-plane adaptation and bounded frontend/browser verification are complete. The remaining task is the stable-release live-provider/security gate.

**Current execution/build evidence is in the completed [single-node simplification verification](../simplify-single-node-platform/verification.md).** It supersedes the pre-cleanup suite counts, image identity and dependency-audit counts below: Rust is removed, default Compose is one application, the current backend Make selection has 10,492 passes, frontend coverage has 1,624 passes, and the development audit has one moderate finding. Optional cluster/Nix/alternate-image checks are no longer default laptop/VPS release prerequisites. The earlier checkpoint rows below are historical evidence, not wholesale reruns after that cleanup.

| Check | Evidence |
| --- | --- |
| Historical pre-adapter upstream baseline | 256 tests passed before provider changes; `/tmp/swissai-baseline-tests.log`. This is not post-change compatibility evidence. |
| Full retained Python unit suite | **10,561 passed, 4 existing skips**, 21 warnings; `/tmp/swissai-unit-latest.log`. The skips cover unavailable host network namespaces and three superseded upstream version-conflict cases. |
| Full frontend suite | **1,624 passed across 189 files**, after the compatible dependency-parent updates; `/tmp/swissai-frontend-latest.log`. |
| Earlier SQLite provider/control-plane selection | **113 passed**, one Starlette/AnyIO deprecation warning; `/tmp/swissai-provider-final.log`. |
| Latest PostgreSQL provider, observations, activity, lifecycle, SDK, monitoring, reports and fold parity | **147 passed**, same warning; `/tmp/swissai-pg-parity.log`. Includes executing shipped monitoring SQL against migrated PostgreSQL, raw/folded source attribution, retained history and stream/settlement fixes. |
| SQLite observation and policy regressions | **26 passed**; `/tmp/swissai-observation-regressions.log`. Includes malformed references, bounded model IDs, terminal usage, TTFT, failed Responses and secret-like identifiers. |
| Production-source scanner scope/config regressions | **3 passed** in `tests/unit/test_check_source_secrets.py`. |
| Fork identity, storage, historical release guards and shell smoke contracts | **67 passed**; `/tmp/swissai-identity-tests.log`. |
| Actual two-process PostgreSQL server test | **1 passed**; `/tmp/swissai-replica-e2e.log`. |
| Earlier focused frontend selection | **90 passed in 12 files**; `/tmp/swissai-ui-final.log`. Covers keys/routing, request details, footer, retention/timeouts, settings permissions/recovery, firewall and telemetry. |
| Earlier changed UI/exports/bootstrap selection | **82 passed in 7 files**; `/tmp/swissai-quality-export-ui.log`. Those files also pass in the latest full frontend run. |
| Production JavaScript dependency audit | `bun audit --prod --json`: **no findings**; `/tmp/swissai-frontend-production-audit.json`. Full development dependency audit remains blocked below. |
| Production-source and image secret scans | Gitleaks: **0 findings across 1,185 files**; `/tmp/swissai-source-secret-scan.json`. All-severity Trivy image secret scan: **0 findings**; `/tmp/swissai-container-secret-scan.json`. Scope and reviewed type-annotation exception are described below. |
| Actual runtime container, served monitoring and live SQLite backup/restore | **1 passed**; `/tmp/swissai-container-e2e.log`. Checks the logical request counter/histogram after durable settlement, not before asynchronous post-send cleanup. |
| Chart-managed two-pod deployment and PostgreSQL dump/restore | **1 passed**; `/tmp/swissai-kubernetes-e2e.log`. Uses an explicitly selected disposable cluster and random test namespace. |
| Python wheel and sdist | `uv build --no-sources --out-dir /tmp/swissai-dist` passed; artifacts include the built React UI. |
| Python Ruff checks and format checks | `uv run ruff check .` and `uv run ruff format --check .` passed. |
| Python typecheck | `uv run ty check` passed. |
| Frontend lint/typecheck/build | `bun run lint`, `bun run typecheck` and `bun run build` passed in `frontend/`. |
| OpenSpec | Strict validation passed for both the `swissai-key-pool` change and spec. |
| Migration topology and schema | One head, `20261028_010000_add_swissai_request_metadata`; topology and fresh migration checks passed, `schema_drift=none`. Default base-ref comparison was skipped because the reference was unavailable. |
| Full lint gate | `make lint` passed with **96/96** settings fields; no simplicity budget increase. |
| Main specification validation | `openspec validate --specs`: **68 passed, 0 failed**, with inherited long-requirement warnings. SwissAI change/spec strict validation also passed. |

The `/tmp` logs are transient local artifacts. The checked-in test cases and commands below are the durable way to reproduce the evidence.

The latest container/SQLite, Kubernetes/PostgreSQL restore and access/MFA browser passes use `localhost/swissai-lb:verification`, image ID `d2497a3396fae3beec9287a5aa1629b2ac2574311693b67d0987234e6a3f0f09`, rebuilt after the monitoring, UI and compatible dependency-parent fixes. The real two-process PostgreSQL test was also rerun successfully against current backend source. The rebuild exhausted the disposable VM's disk once; pruning unused verification-image cache allowed it to complete without increasing its 2-CPU/3-GiB/12-GB allocation or touching application volumes. Earlier CRUD/export browser checkpoints remain separately identified below.

### Backend selection

```sh
uv run pytest -q \
  tests/unit/test_swissai_storage.py \
  tests/unit/test_swissai_policy.py \
  tests/integration/test_swissai_pool.py \
  tests/integration/test_swissai_sdk.py \
  tests/integration/test_dashboard_csrf.py \
  tests/integration/test_health_and_errors.py \
  tests/integration/test_health_probes.py
```

The storage tests check concurrent first-run encryption-key publication and byte-for-byte preservation of rejected legacy SQLite databases. Provider tests include fingerprint deduplication, encrypted storage, specific dashboard read/write permissions, retries, cancellation, deadlines, empty scopes, auth modes, usage settlement, request IDs and malformed/oversized provider errors.

The SDK tests exercise the locked OpenAI Python SDK, JSON and SSE, models, Chat Completions, Completions, Responses, continuation, embeddings, usage capture and failover. They do not establish compatibility with every SDK version, Open WebUI or Codex.

### PostgreSQL and real replicas

Use a dedicated disposable PostgreSQL server, never an operator's production database:

```sh
SWISSAI_LB_TEST_DATABASE_URL="$DISPOSABLE_TEST_DATABASE_URL" \
  uv run pytest -q tests/integration/test_swissai_pool.py

SWISSAI_LB_TEST_POSTGRES_ADMIN_URL="$DISPOSABLE_TEST_ADMIN_URL" \
  uv run pytest -q tests/e2e/test_swissai_postgres_replicas.py
```

The second command creates and drops its own randomly named database and requires CREATE DATABASE permission. It starts two actual `python -m app.cli` processes with separate data directories, shared encryption material and PostgreSQL. It observes:

- Concurrent fresh migration/startup to the same single Alembic head.
- Eight overlapping requests respecting per-key caps of one, with both keys usable concurrently across replicas.
- Continuation ownership surviving a change of serving process.
- 429 rotation and cooldown visibility on the peer, including after restart.
- Client-auth setting propagation to the peer.
- An already-visible SSE stream completing while its process drains after SIGTERM.
- No residual capacity leases and no credential/traceback leakage in server logs.

The retained uvicorn launcher re-raises SIGTERM after graceful shutdown, so the expected process return code is `-SIGTERM`, with an `Application shutdown complete` log and a fully delivered stream. A zero exit code is not the retained launcher's signal contract.

This is bounded local fault evidence, not a load benchmark or proof of every crash/lease-expiry scenario.

## Bugs exposed and corrected by verification

1. **Clock origin mismatch:** the real uvloop launcher immediately returned 504 because a `time.monotonic()` deadline was passed to `asyncio.timeout_at()`, whose loop clock used a different origin. Timeout boundaries now receive the remaining duration while all attempts retain the same absolute monotonic deadline. The real-process regression test catches this failure.
2. **Fresh migration ownership race:** legacy-database inspection now takes the existing cross-process migration lock, avoiding rejection of a peer's partially applied fresh migration.
3. **Response header collision:** the proxy's private header-construction method collided with Starlette's `Response._headers` cache. It was renamed and a product-path test now inspects standard response headers before dispatch.
4. **Shared frontend cache corruption:** the footer stripped routing fields with a partial Zod schema but used the routing form's query key. Both consumers now share the complete schema and query hook; a regression mounts the footer before the form.
5. **Misleading restricted-empty selectors:** an empty restricted scope was labelled “All models/keys” even though it denied all. Existing selector placeholders now describe both their empty trigger and clear-selection entry consistently.
6. **Unsupported UI measurements:** removed subscription-only Appearance controls, suppressed dashboard subscription burn projections, changed model/user-agent distributions to request counts, and removed account-only thread/cache-locality analytics from the SwissAI reports page.
7. **Lost source attribution:** raw and folded usage/report reads now use account identity when present, otherwise SwissAI model-source identity. The retained fold scheduler is again lifespan-owned. Regression checks compare counts, filters and labels before/after folding and after raw-history deletion.
8. **Premature usage and TTFT:** creation counters no longer become terminal usage, and a creation event does not become a generated token. A virtual-clock regression observes the first model output at 500 ms; metadata-only streams leave TTFT unknown. HTTP-200 terminal Responses failures are logged as failed logical outcomes without retrying or invalidating the key.
9. **Partial-stream quota refund:** an interrupted visible stream without terminal usage now settles conservatively rather than refunding a limited client. A gated downstream-send regression proves commitment, one attempt, retained unknown provider usage, charged local budget and zero residual leases.
10. **Malformed ownership fell back to unpinned routing:** invalid/oversized continuation references now fail before dispatch; model metadata is bounded to 512 characters. Credential-like or excessive provider ownership identifiers fail closed with sanitized protocol errors.
11. **Retention dropped labels before logical history:** attempt metadata remains while its request survives the history-fold safety gate, then becomes eligible for bounded pruning.
12. **Incorrect bootstrap instructions:** browser setup exposed legacy environment names and a claim that tokens were logged. All three locales now identify the SwissAI variable and `bootstrap.token` file; rendered screen/dialog regressions cover each locale.
13. **Monitoring referenced retired contracts:** shipped PromQL used nonexistent labels/metrics and SQL referenced retired bridge/prewarm fields. Alerts now count logical errors (including failed HTTP-200 Responses), dashboards use the actual exporter and selected SQL interval, and replicated database gauges are deduplicated before aggregation. Exporter/schema tests and executed PostgreSQL queries cover these contracts.
14. **Metrics configuration weakened network isolation:** enabling scraping opened the entire application HTTP port to every namespace, while the ServiceMonitor selected an unserved port. The universal ingress peer was removed and the monitor now selects the served `http` port and `/metrics`; cross-namespace access requires explicit `extraIngress`. Rendering tests cover this boundary; a policy-enforcing CNI was not tested.
15. **Retained client usage and route recovery:** the adapted client-key dialog again shows token-limit usage, and dashboard pool health no longer eagerly imports the keys route chunk. The full frontend suite now proves these recovery/usage paths without restoring unsupported subscription/automation claims.
16. **Symlinked temporary roots bypassed capture policy comparisons:** traffic-analysis forbidden roots are resolved before comparison. A regression rejects an alias of a forbidden root.

## Browser evidence

The real built React app ran against a fresh disposable database and the local fake upstream. The session used the Bun-global Playwright-backed browser tooling, not an npx-installed Playwright.

Observed operator actions:

- Add a fake upstream key; inspect redacted metadata; pause and resume it.
- Replace its secret, probe it and delete it through the confirmation dialog.
- Save a routing cap, reload the page and observe the persisted value.
- Create a local client key with a model restriction, an assigned SwissAI key and a weekly token limit.
- Enable client-key authentication without losing dashboard access.
- Observe anonymous models access rejected with 401, an allowed generation succeed with 200, and a forbidden model rejected with 403.
- Observe the five-token successful response settle the client counter to five once, and confirm prompt text is absent from request logs.
- Read the corresponding request log and token report; verify the updated reports do not show fabricated `$0` distributions or account-only thread analytics.
- Observe all six key CRUD/probe audit actions, with no fake upstream secret present in the audit response.

The disposable upstream and client credentials were removed after the checks. Screenshots are local artifacts under `/tmp/swissai-verification/screenshots/`, not tracked product files. Expected 401/403 browser console entries came from the deliberate authentication/model-policy checks.

A later browser checkpoint on image `0bd5e6e4f0030329784ed611b1262835dacaec8e59353383f2bbbf8627da515e` additionally observed:

- Initial password setup through the actual bootstrap screen, followed by authenticated dashboard access.
- Three fake-provider requests projected into the quality band with an explicit visible-page sample, known stream TTFT and unknown prices.
- A desktop CSV click producing four lines (header plus three requests), with route/stream facts and no fixture prompt or full credential in logs/CSV.
- A real mobile-context CSV download at **390 × 844**, with document width **390** and no page-level horizontal overflow. Table-local scrolling is not prohibited by this check.
- TOTP enrollment, rejection of an invalid code and successful current-code verification restoring settings access. This is not complete MFA logout/login/recovery coverage.

The browser-only container and generated credentials were destroyed after these checks. Screenshots are `/tmp/swissai-verification/screenshots/swissai-quality-export-latest.png` and `swissai-mobile-quality-latest.png`; the mobile CSV is `/tmp/swissai-verification/mobile-request-export.csv`.

### Current-image access and MFA walkthrough

Bun-global Playwright exercised six passing groups against the latest image and a fresh, local fake-provider database (`/tmp/swissai-verification/access-browser-results.json`):

- Authenticated TOTP enrollment through the API, followed by password login through the actual browser screen.
- Protected inventory denied after password alone, invalid TOTP rejected, and valid fresh-window TOTP restoring protected dashboard access.
- Preset role inventory and a new viewer invite; acceptance through the browser, read-only SwissAI key UI, and server-side rejection of key/settings writes and user-list access.
- Admin disabling the viewer revoking its live session and returning its browser to sign-in. Guest access was disabled for this check so public guest reads could not be mistaken for a surviving user session.
- Admin TOTP recovery revoking a verified viewer session. Password re-login shows the authenticator-enrollment screen; protected inventory remains `403 totp_enrollment_required`, not a second-factor bypass.
- Password-protected guest entry at **390 × 844**, successful permitted reads, rejected writes/user-list access, and document width **390**.

Screenshots are `swissai-viewer-access-latest.png`, `swissai-access-admin-latest.png` and `swissai-guest-mobile-latest.png` under the screenshot directory above. No authenticator enrollment secret is shown in these screenshots. The browser-only container/volume and disposable credentials are removed after verification.

This remains a bounded walkthrough, not exhaustive user/role administration, every mobile page, SSO or all operator workflows.

## Reproducible secret/dependency gates

```sh
uv run python scripts/check_source_secrets.py /tmp/swissai-source-secret-scan.json
cd frontend
bun audit --prod --json
bun audit --json
```

The source scanner snapshots tracked and non-ignored untracked production code, frontend build metadata, deployment files and operational scripts. It excludes test fixtures, generated assets and caches; generated image contents receive a separate all-severity Trivy secret scan. Symlinks fail for explicit review rather than reading outside the repository.

`.gitleaks.toml` retains all default rules and permits exactly the non-secret `private_key: Ed25519PrivateKey` annotation in `app/modules/telemetry/consent.py`. Both the path and full matched text must match. Scope/config tests and an actual CLI negative control verified that a synthetic secret assignment on that same path remains detected. This reviewed false positive is not an advisory/security exemption. The earlier broad scan's fixture/cache matches are not silently characterized as a clean all-repository scan.

Compatible-range JavaScript security updates fixed 100 reported advisories, including the critical `proxy-addr` finding. The direct Zod minimum is now 4.6.7 and the production `source-map-js` dependency is patched. Bun lock and generated Nix inputs were refreshed. Subsequent compatible parent updates to ESLint, typescript-eslint, react-doctor and shadcn reduced the remaining development audit from 14 to 5 advisories; generated Bun/Nix inputs were refreshed again. Full frontend tests, lint, typecheck and build passed afterward. The production audit is clean; the complete development dependency graph still has findings, recorded below.

## Still failing or unverified

- **Full unit and frontend suites now pass**, as recorded above. Historical upload/schema/controller unit coverage was retained through explicitly isolated legacy probes, with additional tests proving the production app does not expose the retired surfaces; retired routes were not re-registered to make tests pass. The complete retained Python integration/bridge selections have not been rerun as a whole. The 147-test PostgreSQL selection is not a blanket CI/compatibility certification.
- Request history, per-key seven-day activity, source filtering and raw/folded source attribution now have regression coverage. Broader aggregate unknown-cost API contracts, previously misattributed experimental fold data, per-attempt usage outside the final terminal observation and scale/latency still need review. No backfill of already-misattributed experimental SwissAI folds was implemented.
- Clock/scheduler seams, lease-renewal loss, expired-lease reclamation, bounded metadata retention, partial-startup teardown and final-settlement cancellation have focused regression evidence. Forced-process-crash and long soak/load/latency evidence remain incomplete.
- Container and Kubernetes execution now use an isolated Podman VM (2 CPUs, 3 GiB RAM, 12 GB disk) and a dedicated kind cluster. Main runtime image, two replicas, fresh migrations, SQLite restore and PostgreSQL restore passed. Distroless and live bundled-database deployment remain unverified.
- **The container security gate is not green:** the latest image still has **46 HIGH package/advisory entries across 10 distinct base-OS advisories**, zero CRITICAL entries and no listed fixes (`/tmp/swissai-container-scan-latest.json`). Earlier fixable Python findings were addressed. A supported Bookworm base also had unresolved findings; no baseline change or blanket waiver was applied. The first refresh failed due to a missing Docker credential helper; rerunning with the isolated empty Docker config refreshed the DB successfully. Stale prior scan output was not counted as new evidence.
- **The current full JavaScript audit is not green:** one moderate minimatch advisory through ESLint remains (`/tmp/swissai-frontend-audit.json`), with no HIGH/CRITICAL development findings. The single-node cleanup retired unused generator/doctor CLIs and their dependency trees; it retained the application's components and lint/type/test gates. Production-only audit has no findings. No forced major-version overrides, downgrade workaround or advisory allowances were applied.
- Release helpers now derive package/chart identity from metadata and have historical/fork regression coverage. The inherited stable-release manifest is history, not proof of a published fork release; maintainer repository/tag baseline selection remains a publication gate.
- Current-image browser evidence now covers password/MFA login, viewer invite/role restrictions, session revocation, admin MFA recovery/enrollment gating and mobile guest access, in addition to earlier CRUD/export checks. Exhaustive administration, every mobile layout and live SSO remain unverified. Open WebUI/Codex smoke tests and load/latency measurement remain outstanding.
- No authorized real SwissAI key, captured profile/error fixtures or live generation canary was available. Stable release remains blocked; no security exceptions were granted.

The OpenSpec change remains open and unarchived. Implementation work can continue locally; stable-release approval is not implied.
