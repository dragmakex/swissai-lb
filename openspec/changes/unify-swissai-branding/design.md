## Scope

Use SwissAI LB as the product name in active UI, CLI help and operator diagnostics, package description, root project guides and the current SwissAI operator documentation linked from README. Keep one concise README attribution line and preserve LICENSE/Git history.

Current operator documentation means the SwissAI operations guide, login recovery, generated settings reference and documentation/deployment/database guide entry points. Historical change artifacts and legacy engineering contracts are not rewritten into misleading promises that unsupported features are SwissAI features.

## Decisions and constraints

- Replace the footer's inherited project link with the SwissAI LB repository; do not add UI or new configuration.
- Version lookup and release-page defaults must reference the same fork. A missing release must continue to return unknown/no-update through existing failure handling.
- Use the fork's operations guide for telemetry help in both UI and startup guidance. Describe the retained external collector honestly; changing branding does not change its address, payload or consent policy.
- Preserve wire headers, stable database IDs/salts, old provider tags and migration files. Those are compatibility data, not visible product branding.
- Update existing callers/tests rather than add a branding framework or dependency.

## Verification

Capture footer before/after images against a local, disposable static UI fixture. Verify desktop/mobile link text and destination, frontend tests/build/lint/types, runtime-version route/service behavior (including missing releases), CLI/help and current-document branding guards, strict change validation and whitespace. Do not touch operator data or running services, and do not push.
