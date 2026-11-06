## ADDED Requirements

### Requirement: SwissAI operator-facing product identity
The active dashboard, CLI help, operator diagnostics, package description and current operator guides SHALL identify the product as SwissAI LB. README SHALL contain exactly one short attribution line naming its upstream basis. LICENSE and Git history SHALL remain intact. Branding changes SHALL NOT rename stable IDs, wire headers, migration history or legacy provider tags.

#### Scenario: Dashboard project link
- **WHEN** an operator views the dashboard footer
- **THEN** the project link reads SwissAI LB and opens `https://github.com/dragmakex/swissai-lb`
- **AND** it does not present a second product brand

#### Scenario: Read the quickstart
- **WHEN** a reader opens README
- **THEN** the project is SwissAI LB and the upstream name appears only on one attribution line

#### Scenario: Check a fork update
- **WHEN** version status is requested
- **THEN** lookup and release links refer to `dragmakex/swissai-lb`
- **AND** unavailable or missing releases preserve unknown/no-update behavior

#### Scenario: Read telemetry help
- **WHEN** an operator follows dashboard telemetry documentation or startup guidance
- **THEN** the link targets the fork's current operations guide
- **AND** telemetry consent, payload and actual collector destination remain unchanged
