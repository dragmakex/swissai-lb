# Contributing to SwissAI LB

This fork keeps the Python application, React dashboard, standard container and single Compose deployment. It does not maintain upstream publishing bots, Helm/Kubernetes, Nix or distroless packaging. Upstream authorship and history remain in LICENSE and Git history.

## Development setup

Use Python 3.13+, uv and Bun:

```bash
uv sync --dev --frozen
(cd frontend && bun install --frozen-lockfile && bun run build)
uv run swissai-lb --host 127.0.0.1 --port 2455
```

Application code is under `app/`, the dashboard under `frontend/`, and tests under `tests/`. `openspec/` owns requirements, change proposals and operational context. Never commit database files, keys, bootstrap tokens or environment files.

## Workflow: OpenSpec-first

1. Read the owning `openspec/specs/<capability>/spec.md` and AGENTS.md.
2. For behavior, API, schema, operator-contract or compatibility changes, create an `openspec/changes/<slug>/` proposal/spec/tasks before coding.
3. Implement the smallest complete change, including external-path regression tests.
4. Validate main specs and changed artifacts strictly; verify before syncing/archiving.

Keep requirements in `spec.md` and narrative guidance beside it in context/ops files. Do not edit `CHANGELOG.md` directly; record change notes in OpenSpec.

## Coding conventions

Follow `.agents/skills/project-conventions/conventions.md` and existing module boundaries. New code is typed; reuse existing clock, cancellation, scheduling and cleanup helpers. Never share one database session across concurrent tasks. Preserve error handling, auth, settlement and data safety when removing or moving code.

```bash
make lint
make typecheck
make test-unit
make frontend-test
make package
```

`make ci` runs the normal local gate. `make ci-extended` adds integration, optional database and standard-container checks; those need their corresponding local services/tools. No check implies live-provider or stable-release certification.

## Commit & PR conventions

Use Conventional Commit titles, one concern per branch/PR, and link the owning OpenSpec change. Issue-resolving PRs must use the exact `Fixes #N` or `Closes #N`; use `Refs #N` for partial coverage. Include what changed, why, tests and remaining risks. No push/publication is implicit in local development.

## Merge gates

Before merging:

1. **Actual current-head GitHub CI is green.** Check `CI Required` and the separate simplicity-budget check, including application, migration, PostgreSQL and security jobs where selected. Local logs are not cloud evidence. Removed upstream release/Helm/Nix checks are not fork jobs; existing cloud branch protection may need a maintainer to retire those requirements explicitly.
2. **Actionable current-head CodeRabbit findings are fixed or explicitly addressed/dismissed in-thread.** A summary is not a substitute for unresolved thread evidence. P1 findings need a fix or applicability justification; P2 findings need a fix or a linked, justified follow-up.
3. **GitHub reports `mergeable=CLEAN`**, with no outstanding requested changes or missing required checks.
4. Behavior/contract changes have an OpenSpec change and strict validation evidence.
5. Issue references and the simplicity gates below are satisfied.

Never claim these gates from local history alone or change repository settings to bypass them.

## Simplicity gates

Follow PRINCIPLES.md P1–P6 and `.github/simplicity-budgets.toml`:

1. New features default off or work zero-config.
2. Every new `SWISSAI_LB_*` setting explains why a hardcoded default is insufficient.
3. README, sample environment, settings count and core navigation stay within their budgets; exceptions require the maintainer-applied `simplicity-budget-approved` label where supported. Do not silently raise caps.
4. Detailed feature/operations documentation goes under its owning OpenSpec capability, not new README sections. Any future rendered `docs/` pages must link to that owner.
5. Dashboard-visible changes include before/after screenshots or a short recording.
6. The dashboard owns behavior settings; name each new setting's tier and preserve code default < env < dashboard precedence.

## Collaborator rules

No self-merge by default: another maintainer merges the author's PR. Split unrelated concerns and large changes (roughly 800 net lines across multiple concerns); a cohesive single-capability change is judged by scope, not line count alone.

## Bus factor escape hatch

After **more than 14 days** awaiting maintainer merge, the author may self-merge only with **all gates met**, no outstanding requested changes and no active collaborator objection. The PR must contain a comment explicitly invoking this clause and linking to when its gates first went green. This is not permission to skip review or checks.

## Release process

This fork currently has no automated publication pipeline. Do not publish upstream packages/images/charts or assume upstream maintainers operate this fork. Keep Python, frontend and lock metadata consistent; the retained unit test checks them. Stable release readiness remains governed by the SwissAI OpenSpec evidence requirements, not by a successful local build. Historical release automation is preserved in Git history.

## Security issues

Do not post credentials or vulnerability details publicly. Use this repository's private security-reporting channel if enabled; otherwise contact its maintainer privately. Never send fork-specific secrets to an upstream project. See [SECURITY.md](SECURITY.md).
