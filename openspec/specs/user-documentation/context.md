# SwissAI LB documentation

Owner: [user-documentation specification](spec.md). The [delivery cleanup](../../changes/trim-unused-delivery-tooling/specs/user-documentation/spec.md) replaces the inherited documentation-site contract; the [branding change](../../changes/unify-swissai-branding/specs/swissai-key-pool/spec.md) defines the current product identity.

## Purpose

Keep startup simple and keep detailed operational guidance close to the requirements it explains. README is the quickstart, not an exhaustive manual. SwissAI LB is the user-facing product name; README contains one short upstream-attribution line, and LICENSE/Git history retain authorship.

## Current guides

- [SwissAI operations](../swissai-key-pool/context.md): supported HTTP routes, key routing, authentication, storage, backups, telemetry and release limits.
- [Login recovery](../admin-auth/ops.md): host recovery commands and lost-factor/provider recovery.
- [Settings reference](../configuration-tiers/reference.md): generated accepted names, types and defaults, including inherited advanced settings that do not enable unsupported inference routes.
- [Database operations](../database-backends/context.md): SQLite-first startup and optional PostgreSQL settings.

There is no maintained external documentation site or separate translated README. Historical change artifacts and legacy engineering contracts remain for provenance and compatibility work; they are not a promise that every inherited feature is enabled.

## Decisions and constraints

- Keep README within its existing budget, with source/container startup and links to these guides.
- Keep normative requirements in `spec.md` and narrative context beside the owning capability.
- Keep `.env.example` commented so copying it does not silently alter defaults.
- Generate the settings reference from code; drift tests and the unchanged field-count budget remain.
- Use this repository for project, help and release links. A missing release means unknown/no-update, not a reason to advertise another application's version.
- Keep actual collector destinations and compatibility identifiers truthful when changing visible branding.

## Example

An operator asks how to recover a lost authenticator. README links directly to the login-recovery guide, which gives `uv run swissai-lb admin reset-password <username> --clear-two-factor` and explains the security consequences. No documentation-site build or account credentials are needed to read it.
