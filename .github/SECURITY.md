# Security policy

Do not publish vulnerabilities, credentials, bootstrap tokens, database files or private inference content in issues, discussions or pull requests.

Report a SwissAI LB vulnerability through **this repository's** Security → Advisories → Report a vulnerability, if private reporting is enabled. Otherwise contact this fork's maintainer privately to arrange a secure channel. Do not send fork-specific secrets to upstream codex-lb maintainers.

Include the affected version/commit, source or standard-container deployment, impact, minimal reproduction and sanitized diagnostics. Remove all keys, passwords, tokens and private request bodies. A proposed fix is welcome.

This is a development-beta fork. No stable support window, response-time SLA, published image or upstream-maintainer support is implied. Fixes target the current fork; coordinated disclosure and any publication must be agreed with its maintainer.

The application/dashboard, authentication, key routing, storage and standard build are in scope. Provider-service issues belong with that provider. Third-party dependency issues should be reported upstream as well when appropriate.
