## REMOVED Requirements

### Requirement: Provider-appropriate reporting
**Reason**: The original requirement includes Helm NetworkPolicy, ServiceMonitor and chart-owned monitoring scenarios that are explicitly retired.
**Migration**: Keep truthful application reporting under the focused requirement below; manage any monitoring manifests independently.

## ADDED Requirements

### Requirement: SwissAI reporting remains truthful without chart artifacts
Report distributions SHALL use request counts rather than inferred SwissAI costs. The dashboard SHALL NOT expose subscription projections or account-only locality analytics as SwissAI measurements. Runtime metrics SHALL remain available, but this fork SHALL NOT ship Helm alert/Grafana artifacts.

#### Scenario: Upstream-key filters survive history folding
- **WHEN** SwissAI request history is filtered by key before and after report folds
- **THEN** counts, model options and attribution remain unchanged

#### Scenario: SwissAI usage without authoritative pricing
- **WHEN** SwissAI requests have no authoritative pricing
- **THEN** reports omit fabricated dollar costs

## MODIFIED Requirements

### Requirement: Consistent fork identity
Runtime, Python package, frontend and Python lock metadata SHALL identify the SwissAI fork consistently. Operator configuration SHALL use the `SWISSAI_LB_` namespace. Version consistency SHALL NOT depend on charts or removed publication machinery.

#### Scenario: Bootstrap guidance identifies the secret source
- **WHEN** a remote operator sets the initial dashboard password
- **THEN** guidance points to `SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN` or the data directory's `bootstrap.token`, not plaintext server logs

#### Scenario: Inspect a fork release candidate
- **WHEN** the repository version check runs
- **THEN** it checks runtime, Python/frontend metadata and the SwissAI lockfile entry without charts or release-tag publication helpers

### Requirement: Simple single-node operation
The default SHALL remain one Python process serving inference and the built dashboard with persistent SQLite storage. The fork SHALL ship one standard Dockerfile and one Compose file as optional packaging, and SHALL NOT ship Kubernetes/Helm, Nix or distroless variants. Default Compose SHALL start only the app with named storage and loopback HTTP. Existing explicit development/PostgreSQL profiles MAY remain.

#### Scenario: Start on a laptop
- **WHEN** an operator follows the local quickstart
- **THEN** one process serves the dashboard and SwissAI HTTP routes without external database, Rust, cluster or Nix tooling

#### Scenario: Default Compose on a VPS
- **WHEN** default Compose starts without `.env.local`
- **THEN** only the app runs, the data volume persists and HTTP is loopback-published

#### Scenario: Development and optional infrastructure
- **WHEN** an operator runs default development checks
- **THEN** no retired Rust/cluster/Nix tooling is required and development/PostgreSQL profiles remain explicit opt-ins
