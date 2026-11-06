## REMOVED Requirements

### Requirement: Helm chart is organized around install modes
**Reason**: Kubernetes/Helm packaging is retired from this fork.
**Migration**: Use the Python application or standard Dockerfile and single Compose file.

### Requirement: Helm install modes are smoke-tested
**Reason**: The chart, kind harness and dedicated chart checks are removed together.
**Migration**: Use the retained single-node application/container checks.

### Requirement: Helm support policy is pinned to modern Kubernetes minors
**Reason**: This fork no longer ships Kubernetes packaging.
**Migration**: Existing cluster operators must manage their own deployment manifests.

### Requirement: Static bridge ring overrides are guarded at render time
**Reason**: Chart rendering is retired; application validation remains unchanged.
**Migration**: Do not rely on a shipped Helm values contract.

### Requirement: Documented bridge ring and advertise URL examples pass application validation
**Reason**: The retired upstream chart/docs examples are not SwissAI deployment instructions.
**Migration**: Use the single-node quickstart; runtime validation remains.

### Requirement: External secret references support provider-native layouts
**Reason**: Helm/ExternalSecret templates are removed.
**Migration**: Manage deployment secrets outside the repository using the supported application settings.

### Requirement: Helm PostgreSQL capacity guidance accounts for both application pools
**Reason**: Helm packaging is removed.
**Migration**: Optional PostgreSQL application support remains; size it for its actual application pools.

### Requirement: Helm Grafana dashboard titles are configurable
**Reason**: Chart-owned Grafana artifacts are removed.
**Migration**: Runtime metrics remain available for independently managed monitoring.

### Requirement: Helm preStop shares the application drain deadline
**Reason**: Chart lifecycle hooks are removed, not the application's drain lifecycle.
**Migration**: Keep the project-owned application launcher for process shutdown.

### Requirement: Nix flake provides reproducible development and execution paths
**Reason**: Nix packaging and bun2nix generation are retired.
**Migration**: Use uv/Bun lockfiles or the standard container build.

### Requirement: Official Linux container packages locked native egress
**Reason**: The native worker was removed by the earlier single-node simplification.
**Migration**: Use the retained Python transports and standard image.

### Requirement: Rust migration uses one final-state workspace
**Reason**: Rust migration is not the direction of this Python fork.
**Migration**: Use the Python application; no Cargo workspace is required.

### Requirement: External database network egress matches the connection source
**Reason**: This requirement governs removed chart NetworkPolicy templates.
**Migration**: Manage external database networking explicitly outside the retired chart.

### Requirement: Helm chart renders no pre-1.13 controller-migration shim
**Reason**: The entire chart is retired.
**Migration**: Keep historical upstream chart upgrades outside this fork's single-node delivery contract.

### Requirement: Operator metrics and log configuration fails closed
**Reason**: The upstream contract includes validation by a retired Helm values schema.
**Migration**: Preserve application validation through the focused requirement below.

## ADDED Requirements

### Requirement: Application metrics and log configuration fails closed
The application MUST accept metrics ports only in inclusive `1..65535` and log format only as `text` or `json`. Invalid values MUST produce field-specific validation errors before metrics startup or formatter selection. Existing main/metrics collision rejection MUST remain. No chart schema is required.

#### Scenario: Impossible metrics port is rejected
- **WHEN** a metrics port is zero, negative or above 65535
- **THEN** application settings validation identifies `metrics_port`

#### Scenario: Unknown log format is rejected
- **WHEN** log format is neither text nor json
- **THEN** application settings validation identifies `log_format`

## MODIFIED Requirements

### Requirement: Docker Compose deployments are declared single-replica
The repository SHALL ship one `docker-compose.yml`. Its default SHALL start only the standard-image application, use persistent named storage and publish HTTP on loopback. Development and PostgreSQL services SHALL remain explicit profile opt-ins. A separate production Compose variant SHALL NOT be maintained.

#### Scenario: Compose files carry the guardrail statement
- **WHEN** the sole `docker-compose.yml` is inspected
- **THEN** it documents its single-replica SQLite topology and warns against scaling it
- **AND** default startup without profiles or a local env file starts only the app with named storage and loopback HTTP

### Requirement: Owned launch paths preserve raw peer before proxy projection
Every retained project-owned launcher SHALL disable server-level proxy projection. Outermost application middleware SHALL preserve the raw HTTP/WebSocket peer and apply Uvicorn-compatible projection exactly once; downstream consumers SHALL still see the projected client/scheme. Trust SHALL come from `forwarded_allow_ips`, accepting the bare `FORWARDED_ALLOW_IPS` and `SWISSAI_LB_FORWARDED_ALLOW_IPS` aliases from process/env files without direct middleware environment reads. Unset, empty, wildcard and explicit hosts/networks SHALL retain Uvicorn's existing semantics. The standard image and Compose SHALL delegate to the project-owned CLI without a command override.

#### Scenario: Standard container launch
- **WHEN** the standard image starts through Compose
- **THEN** the entrypoint launches `python -m app.cli` without a Compose command override

#### Scenario: Owned launchers disable early projection
- **WHEN** the source CLI or standard container starts the application
- **THEN** outer server projection is disabled and capture/projection runs exactly once

#### Scenario: HTTP and WebSocket preserve both identities
- **WHEN** a trusted peer sends valid forwarded client/proto headers over HTTP or WebSocket
- **THEN** the raw peer is preserved and downstream code observes the projected client/scheme

#### Scenario: Forwarded allowlist behavior is unchanged
- **WHEN** the allowlist is unset, empty, wildcard or explicit hosts/networks
- **THEN** projection follows Uvicorn trust semantics

#### Scenario: Prefixed alias is honored
- **WHEN** `SWISSAI_LB_FORWARDED_ALLOW_IPS` is set without its bare alias
- **THEN** that value is honored and both accepted names appear in the generated reference
