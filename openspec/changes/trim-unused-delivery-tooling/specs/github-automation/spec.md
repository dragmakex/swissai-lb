## REMOVED Requirements

### Requirement: PR metadata edits do not restart the CI matrix
**Reason**: The original contract also requires retired release-guard workflows and contexts.
**Migration**: Preserve metadata-only CI stability through the focused fork requirement below, without publication guards.

### Requirement: Automated review summaries avoid PR-body CI restarts
**Reason**: The original contract couples review summaries to retired release-evidence automation.
**Migration**: Retain walkthrough summaries and review gates without upstream release automation.

## ADDED Requirements

### Requirement: Fork CI does not publish or require retired delivery tooling
Repository workflows SHALL retain application tests, lint/type/build/package, migrations, security, simplicity budgets and OpenSpec checks. They SHALL NOT ship upstream release/publishing, metadata-update, issue/PR-labeler, stale or contributor-bot workflows, or require Helm, kind, Nix or distroless jobs. Remaining CI dependencies and changed-area filters SHALL name only retained jobs/surfaces.

#### Scenario: Inspect the fork workflow graph
- **WHEN** repository workflows are parsed
- **THEN** job dependencies resolve and none require retired delivery jobs or publish upstream packages/images/charts

#### Scenario: GitHub changed-file API outage
- **WHEN** the changed-file API fails after retries
- **THEN** the detector selects every retained CI area rather than silently skipping checks

### Requirement: Fork CI ignores metadata-only edits
The CI matrix MUST NOT subscribe to pull-request `edited` events. New commits SHALL run normal path-filtered checks and superseded runs MAY be cancelled. Removed release-guard contexts SHALL NOT remain in the CI graph.

#### Scenario: PR description changes during CI
- **WHEN** the title/body changes without a new commit while CI is running
- **THEN** CI is neither restarted nor cancelled and existing current-head checks remain authoritative

#### Scenario: New commit
- **WHEN** the pull request receives a new commit
- **THEN** normal CI runs for that head

### Requirement: Fork review summaries stay in walkthrough comments
Retained CodeRabbit configuration SHALL place generated summaries in its walkthrough comment rather than updating the PR body. Removing upstream publication automation SHALL NOT waive actionable review findings.

#### Scenario: Review completes
- **WHEN** CodeRabbit generates its summary
- **THEN** its configured destination is the walkthrough comment and it does not trigger a CI matrix restart
