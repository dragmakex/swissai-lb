# Design

## Scope and decisions

Keep one Python/React application, the standard Dockerfile and one loopback-published Compose file (SQLite server by default; existing development/PostgreSQL profiles remain optional). Remove unsupported packaging rather than retaining inert wrappers. Remove upstream publishing and maintainer bots; retain ordinary application CI and its security/migration/architecture gates.

Delete tests only when their entire subject is removed. Adapt mixed tests to the surviving launcher/image/Compose contracts. Keep application storage/version checks, shared protocol fixtures and all runtime regressions. Chart-only monitoring SQL tests retire with the chart; runtime metrics and request/report tests remain.

Replace the obsolete documentation site rather than editing its dozens of upstream pages. Preserve the generated settings reference in `openspec/specs/configuration-tiers/reference.md`, keeping drift coverage and the setting-count budget. Move legacy Codex config examples used by compatibility tests to `tests/fixtures/codex/`. Preserve operator recovery guidance under OpenSpec before removing the old SSO document. Historical archived specs and migration files are not rewritten to erase history.

Version checking reuses the existing storage/package unit regression and adds the `uv.lock` assertion there; no replacement release helper is needed. Release-tag parsing, chart version synchronization and publication guards are not fork requirements. Dependency locks are regenerated without upgrading unrelated packages.

## Safety and limits

- Do not delete database/encryption/bootstrap material, named volumes, operator backups, LICENSE or migrations.
- Do not commit, push, publish, archive changes, change GitHub settings, restart services or manipulate container VMs.
- Ignore private runtime material and generated output; keep lockfiles, sample environment configuration and source fixtures visible.
- Shared dormant ChatGPT and enterprise runtime modules are explicitly outside this cleanup. Retaining their tests does not promise those routes are production-enabled.
- Existing branch protection may name removed jobs; report that administrative follow-up rather than changing cloud settings.

## Verification

Run focused repository-contract/settings/version/secret-scan tests first, retained backend unit and frontend checks, package build, strict OpenSpec validation, workflow syntax/reference checks and `git diff --check`. Verify ignored secret/data samples and non-ignored source/lockfiles with `git check-ignore`. Report any unavailable container/cloud checks without claiming a live deployment or stable-release certification.
