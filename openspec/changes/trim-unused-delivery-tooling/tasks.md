## 1. Packaging and automation

- [x] 1.1 Remove Helm/kind, Nix/bun2nix, distroless and the production Compose variant with their dedicated helpers/tests.
- [x] 1.2 Remove upstream publishing/maintainer automation and update CI changed-area/dependency contracts while preserving application quality gates.
- [x] 1.3 Keep lightweight Python/frontend/lock version consistency checks without chart/release machinery.

## 2. Documentation and repository hygiene

- [x] 2.1 Replace stale site/translations with a short README; preserve generated settings/recovery documentation under OpenSpec and test-used examples as fixtures.
- [x] 2.2 Rewrite `.gitignore` for private runtime material/generated output and verify source/lockfiles remain visible.

## 3. Verification

- [x] 3.1 Update mixed regression tests and dependency locks; run focused checks, retained unit/frontend/package gates and strict OpenSpec validation.
- [x] 3.2 Record exact evidence, remaining references/limits and unchanged runtime/operator-data safety boundaries. Do not commit or push.
