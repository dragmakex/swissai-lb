## REMOVED Requirements

### Requirement: Documentation site builds strictly and deploys from main
**Reason**: The inherited MkDocs site and upstream Pages publication are retired.
**Migration**: Use README for startup and owning OpenSpec context/reference files for operational detail.

### Requirement: README stays a quickstart
**Reason**: The upstream contract requires a retired site, ChatGPT client guide, translated README and contributor-bot block.
**Migration**: Use the focused SwissAI quickstart requirement below. Preserve attribution in LICENSE and Git history, not a generated bot table.

## ADDED Requirements

### Requirement: SwissAI README is a simple quickstart
README SHALL contain a brief SwissAI purpose, source and standard-container startup, dashboard/client-auth pointers, persistence/security cautions and upstream attribution. It SHALL remain within existing simplicity budgets. The stale translated README and generated contributor-bot block SHALL NOT be required. It SHALL NOT advertise removed ChatGPT inference or delivery tooling.

#### Scenario: Start from source
- **WHEN** a reader follows README source startup
- **THEN** it installs locked Python dependencies, builds the dashboard with locked Bun dependencies and starts the project-owned SwissAI CLI

#### Scenario: Start the standard container
- **WHEN** a reader follows README Compose startup
- **THEN** it uses the sole Compose file, builds locally and keeps named data storage

## MODIFIED Requirements

### Requirement: Docs pages link their governing OpenSpec capability
Normative requirements SHALL remain in `openspec/specs/*/spec.md`; narrative operations, recovery and generated reference material SHALL live alongside their owning capability and link to it. Archived historical docs SHALL NOT be presented as the current SwissAI operator guide.

#### Scenario: Behavior page carries a spec link
- **WHEN** a reader follows README operational links to a behavior page
- **THEN** its target exists under OpenSpec and identifies the governing capability

### Requirement: .env.example is a commented zero-drift sample
`.env.example` SHALL contain only commented-out values matching code defaults, including the `SWISSAI_LB_` namespace. It SHALL retain the commented single-instance leader-election escape hatch. Copying it verbatim SHALL preserve no-configuration behavior.

#### Scenario: Copying the sample changes nothing
- **WHEN** the operator copies `.env.example` to `.env.local` without uncommenting values
- **THEN** effective settings do not change and leader election remains enabled

#### Scenario: Leader-election escape hatch stays documented
- **WHEN** `.env.example` is read
- **THEN** it includes `# SWISSAI_LB_LEADER_ELECTION_ENABLED=false` without an active assignment disabling leader election

### Requirement: Generated settings reference stays in sync with the code
`openspec/specs/configuration-tiers/reference.md` SHALL be generated from `Settings.model_fields` by the existing generator and linked from README. It SHALL identify itself as generated, link its owning capability, list accepted environment aliases/types/defaults, startup guards, process-level conventions and removed names from code. Drift tests and the unchanged settings-count budget SHALL remain. The reference SHALL distinguish retained inherited settings from production-enabled SwissAI inference features.

#### Scenario: Settings change without regeneration fails CI
- **WHEN** settings change without updating the generated reference
- **THEN** unit tests fail on output drift

#### Scenario: Reference page is reachable and generated
- **WHEN** a reader follows README's settings link
- **THEN** the generated reference exists under its owning capability, identifies its generator and links that owner without requiring a site build

#### Scenario: Settings surface growth trips the ratchet
- **WHEN** the settings count exceeds the unchanged budget
- **THEN** the ratchet test fails rather than silently increasing the cap

#### Scenario: Aliased setting renders every env name
- **WHEN** a setting has explicit validation aliases
- **THEN** its row lists the primary name and every accepted alias

#### Scenario: Process-level conventions are documented but not settings
- **WHEN** the retained application reads a third-party or POSIX environment convention
- **THEN** the reference identifies its consumer without counting it as a setting

#### Scenario: Removed names are listed without a deprecated-alias section
- **WHEN** the page is regenerated
- **THEN** its Removed section lists names from `_REMOVED_SETTINGS` and has no separate deprecated-env-alias list
