# Tasks

## 1. Retire unused native transport

- [x] 1.1 Remove native dispatch/IPC/framing branches and preserve the Python clients' transport error, cancellation and cleanup semantics; verify client tests and Python typecheck.
- [x] 1.2 Remove Rust workspace/toolchain/worker-only fixtures, tests and benchmarks; preserve shared Python golden/protocol assertions and verify no executable Rust dependency remains in application source.
- [x] 1.3 Remove Rust build/audit/changed-area CI requirements and keep default Make checks independent of optional cluster/database tools; verify workflow/changed-area and packaging regression tests.

## 2. Simplify operator and frontend defaults

- [x] 2.1 Make default Compose one persistent application, loopback HTTP and no required env file; preserve opt-in development/PostgreSQL profiles and volume names; verify Compose contract tests and resolved configuration.
- [x] 2.2 Remove unused generator/doctor CLIs, refresh Bun/Nix lock inputs and retain lint/type/test tooling; verify frozen install, frontend suite/build and dependency audits.
- [x] 2.3 Update local/VPS instructions and SwissAI specs/context to describe the supported simple default, security boundaries and scoped release evidence; verify strict OpenSpec validation.

## 3. End-to-end safety

- [x] 3.1 Run full retained unit/frontend suites and supported provider/control-plane integration checks, build the package/image, and repeat actual container key routing/persistence/backup restore; record observed evidence and remaining external blockers without claiming a live-provider pass.

Observed scope and remaining release blockers: [verification.md](verification.md).
