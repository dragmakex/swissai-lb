## ADDED Requirements

### Requirement: Simple single-node operation
The default deployment SHALL run one application process serving inference and the built dashboard with persistent SQLite storage. It SHALL NOT require Rust, a native transport worker, PostgreSQL, Kubernetes, Nix, or a separate frontend server. Docker SHALL remain optional packaging of the same application.

#### Scenario: Start on a laptop
- **WHEN** an operator installs the Python dependencies, builds the dashboard and starts the documented local command
- **THEN** one application serves the dashboard and SwissAI HTTP routes without a Rust installation or external database

#### Scenario: Default Compose on a VPS
- **WHEN** an operator starts default Compose without a local environment file
- **THEN** only the application starts, its data persists in a named volume, and its published HTTP port binds to loopback for use behind a TLS reverse proxy or SSH tunnel

#### Scenario: Development and optional infrastructure
- **WHEN** the operator runs the default development checks
- **THEN** no Cargo, Rust worker or local Kubernetes cluster is required; frontend development and PostgreSQL remain explicit opt-ins

## MODIFIED Requirements

### Requirement: Evidence before stable release
A stable release SHALL require fake-upstream fault and lifecycle tests, dashboard browser verification, single-node container and migration checks, backup/restore, secret/dependency scans and an authorized live canary. Local lint or build success alone SHALL NOT be called production certification. Optional cluster, alternate-image and external-database checks SHALL NOT be prerequisites for the default laptop/VPS deployment.

#### Scenario: Local tests pass without a live canary
- **WHEN** local tests pass but production deployment or authorized live checks have not run
- **THEN** release status remains a development beta with the missing evidence recorded

#### Scenario: Optional deployment tooling is absent
- **WHEN** the supported single-node release checks run without Rust, Helm, kind or an external PostgreSQL service
- **THEN** those absent optional tools do not block the default laptop/VPS checks
