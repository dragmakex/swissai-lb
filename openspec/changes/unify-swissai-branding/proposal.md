## Why

The operator wants SwissAI LB to be the sole user-facing product name, with one short README attribution line. Dashboard links, CLI help, update metadata and a few current guides still show the inherited name or point to the wrong repository.

## What Changes

- Use SwissAI LB in active dashboard branding, CLI/operator diagnostics and current operator guides.
- Keep one README line: based on the upstream project; preserve LICENSE and Git history.
- Point project/release links and version lookups at `dragmakex/swissai-lb`.
- Link telemetry help to this repository's current operational guide without changing consent, transmitted payloads or collector destinations.
- Preserve protocol/header names, stable IDs, legacy provider tags, migration history and historical engineering records rather than breaking compatibility for cosmetic renaming.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `swissai-key-pool`: consistent operator-facing identity and repository links.

## Impact

Dashboard footer/help links and tests, runtime version metadata/tests, CLI help and human-readable errors, package description and current operator documentation. No credential, database/schema, routing, authentication, telemetry-consent or publication change. No push or service restart.
