# Proposal

## Why

The operator wants a small, self-hosted SwissAI key rotator and dashboard for a laptop or VPS. The fork still carries an unused Rust transport and makes enterprise deployment tooling part of ordinary development checks; preserving those moving parts does not improve the SwissAI request path.

## What Changes

- **BREAKING:** retire the Rust workspace, native-egress worker/IPC adapter, its optional transport branches, native-only fixtures/tests, and Rust build/audit/CI requirements. Keep the existing Python transports and their safety/cleanup behavior.
- Make one Python process plus its built React assets and persistent SQLite directory the supported default. Keep Docker/Compose as optional packaging, not a required service stack.
- Start only the application with default Compose; make frontend development and PostgreSQL explicit optional profiles, require no local env file, bind the published application port to loopback, and remove the retired OAuth callback port.
- Remove unused frontend code-generation/doctor CLIs and their scripts, not the generated components, ESLint, typecheck, or test gates.
- Keep existing database migrations, encryption, authentication, dashboard, key routing, limits, logs/reports and backups intact. Existing advanced deployment artifacts are optional, not prerequisites or universal release gates.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `swissai-key-pool`: define Python-only, single-node laptop/VPS operation and scope required release evidence to the supported default deployment.

## Impact

Rust source/toolchain/lock/policy files; Python native transport callers; native-only test fixtures and benchmarks; Makefile and CI routing; frontend development dependencies; Compose defaults; README and owning OpenSpec context. No schema migration or operator-data deletion. The original key-pool change stays open until its separate live-provider and security gates are actually satisfied.
