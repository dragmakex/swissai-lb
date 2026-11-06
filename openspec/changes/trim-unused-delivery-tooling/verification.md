# Verification: unused delivery tooling cleanup

## Implemented scope

- Removed Helm/Kubernetes/kind, Nix/bun2nix, distroless, duplicate production Compose and their dedicated scripts/tests/CI jobs.
- Retained standard Dockerfile/entrypoint, the single default-loopback Compose file, optional development/PostgreSQL profiles, runtime metrics and normal application/security/migration/package checks.
- Removed upstream release/publishing/metadata/labeler/stale/contributor automation and upstream CODEOWNERS. Kept useful dependency-security updates and CodeRabbit review configuration; review gates were not waived.
- Removed the obsolete MkDocs site/translations and upstream screenshot generator. README is 43 lines with four h1/h2 headings. Preserved generated settings reference and dashboard recovery guidance under their OpenSpec owners. Moved test-used legacy configs byte-for-byte to test fixtures.
- Moved the original root product brief under the original change, marked as historical planning input, and corrected active links. It is not the current operator contract.
- Rewrote ignore rules for private keys, env files, SQLite/WAL files, bootstrap material, logs/captures and generated output. Added corresponding standard-image build-context exclusions.
- Tightened the root allowlist to the actual 27-entry source snapshot, including LICENSE and source-secret configuration. Numeric README/env/nav/settings budgets are unchanged.
- Removed 16 documentation-only Python lock packages and bun2nix/sade/mri from the frontend lock. No retained Python package version changed; frontend lock diff contains deletions only. Upstream authorship remains; upstream authors are no longer falsely listed as this fork's maintainers.

## Fresh checks

Logs: `/tmp/swissai-trim-unused-delivery/` (local artifacts, not publication material).

| Check | Evidence |
| --- | --- |
| Full retained unit/simulation/request-options selection | **10,299 passed, 6 skipped, 1 existing xfailed, 21 warnings**; `unit.log` |
| Frontend lint, typecheck, full test selection | **1,624 passed / 189 files**; `frontend.log` (test run without coverage instrumentation; thresholds unchanged) |
| Final focused repository/settings/version/probe/pool/SDK/lifecycle/product-path login-recovery selection | **127 passed**; `regressions.log`, including the later-added current-source root inventory check |
| `make lint` | Architecture/cancellation/timing/settings checks, local migration topology and Ruff pass; **96/96 settings**, **265 revisions**, original SwissAI head preserved |
| `make typecheck` and final direct Ty/Ruff checks | Pass |
| `make package` | Builds dashboard, sdist and wheel; wheel frontend assets verified, including a final rerun after the brief/metadata moves (`package-final.log`) |
| Source secret scan | **0 findings / 1,118 production-source files**; `source-secrets.log` and redacted JSON |
| Strict changed OpenSpec validation | All four active SwissAI changes pass, including this cleanup |
| Canonical OpenSpec validation | Default validation: **68 passed**. Additional global `--strict` run: **9 passed / 59 failed** because existing main specs contain long-requirement warnings; see limits below. |
| Workflow contracts | All three surviving workflow YAML files parse; job dependencies resolve; no retired delivery jobs remain |
| Fixture relocation | Both legacy TOML fixtures byte-identical to source archive copies |
| Ignore and README contracts | Private samples ignored; source/lockfiles/sample env/fixtures visible; README local links exist |
| Whitespace | `git diff --check` passes |

## Limits and unchanged risks

- At the cleanup-verification checkpoint, no commit, staging, push, publication, repository-setting change or service restart had occurred. Later local version-control preparation requires separate operator authorization. Neither native listener nor operator database/encryption/bootstrap/backup data was intentionally changed. Existing unrelated worktree changes were preserved; source-only copies of removed paths are under `/tmp/swissai-trim-unused-delivery/` for recovery.
- The first pre-commit simplicity-budget run read the pinned upstream **committed HEAD**, so it reported historical deleted root entries (initially `crates`) rather than the prepared source snapshot. The separate current-snapshot test proves all 27 surviving source root entries fit the tightened allowlist. A normal HEAD-based run can check the committed snapshot after the local commit; no allowlist waiver or synthetic passing cloud check was used.
- Global strict main-spec validation is **not green**: 59 existing capabilities contain requirements over 500 characters, and strict mode treats those warnings as failures. Their normative main `spec.md` files were not rewritten in this cleanup. Normal canonical validation and strict validation of all four active SwissAI changes pass; do not describe that as a global strict pass or waive the old findings.
- Local migration topology passes, but the base-ref comparison reports **ref unavailable**. No migration was added or rewritten in this cleanup, and no main fetch was performed.
- No fresh container/Compose deployment, Apple-container networking, image vulnerability scan, PostgreSQL matrix, full legacy integration/bridge suite or browser/soak/live-provider run. Apple host networking remains a separately known blocker. Earlier base-image vulnerabilities and the development minimatch advisory are not declared fixed by deletion/build success.
- This is not stable-release certification. The original broader SwissAI release-evidence task remains open; changes remain unarchived. Existing cloud branch protection may still require removed upstream jobs until a maintainer deliberately updates it.
- Live client-key authentication was previously disabled and was not changed here. Enable it and rotate any chat-exposed local credential before wider exposure.
