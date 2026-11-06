# Proposal

## Why

The laptop/VPS SwissAI fork still carries upstream cluster/Nix/alternate-image packaging, publishing bots and documentation for retired ChatGPT features. These increase maintenance and make a first GitHub push misleading. The operator explicitly requested their removal, a clean ignore policy and a short README, without pushing or changing running services/data.

## What Changes

- Remove Helm/Kubernetes, Nix, distroless and the separate production Compose variant, including their dedicated scripts/tests and CI requirements.
- Remove upstream release/publishing, labeler/stale/contributor-bot and metadata-update automation and unused helpers. Keep application CI, migration/security/package checks, simplicity budgets and OpenSpec validation.
- Remove the stale MkDocs site and translated README. Preserve useful generated settings documentation under OpenSpec and move legacy example files still used by tests into test fixtures.
- Replace README with a short source/standard-container quickstart and links to owning operational context. Rewrite `.gitignore` to exclude credentials, databases, captures, caches and generated output without hiding source/lockfiles/fixtures.
- Keep version consistency checking for the Python/frontend/lock metadata without a chart or publishing pipeline.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `swissai-key-pool`: remove chart identity/provisioning claims from the fork's supported delivery contract.
- `deployment-installation`: retire removed packaging/install contracts while preserving standard-image, data-directory, launch and optional database safety.
- `github-automation`: retire publishing/maintainer-bot and optional delivery jobs while retaining read-only CI and quality checks.
- `user-documentation`: replace the upstream documentation site with a slim README and OpenSpec operational/generated reference documentation.

## Impact

Repository packaging, CI/scripts, documentation, frontend generator metadata, Python documentation-only dependencies and tests for retired surfaces. Runtime inference/auth/persistence code, database migration history, LICENSE and upstream attribution remain. No commit/push, service stop/restart, database modification, image publication or machine-level cleanup.
