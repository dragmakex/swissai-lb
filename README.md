# SwissAI LB

A small SwissAI API-key load balancer with a web dashboard. Add multiple SwissAI keys, rotate requests across them, and inspect request history. One Python process; SQLite by default. **Development beta.**

## Run locally

Requires Python 3.13+, [uv](https://docs.astral.sh/uv/) and [Bun](https://bun.sh/).

```bash
uv sync --frozen
(cd frontend && bun install --frozen-lockfile && bun run build)
uv run swissai-lb --host 127.0.0.1 --port 2455
```

Open **http://127.0.0.1:2455**, set your dashboard password and add upstream SwissAI keys under **Keys**. If port 2455 is occupied, pass `--port 2456` instead.

Use **http://127.0.0.1:2455/v1** as your client's OpenAI-compatible base URL. Create a local client key in the dashboard and **enable client-key authentication**; dashboard login and inference authentication are separate. The default upstream is `https://api.swissai.svc.cscs.ch/v1`.

## Container

With Docker and Compose installed:

```bash
docker compose up -d --build
```

This builds the same application locally, publishes `127.0.0.1:2455` and keeps data in the `swissai-lb-data` volume. No environment file is required. Stop with `docker compose down` **without `-v`** to preserve data.

For a VPS, keep the loopback binding and use a TLS reverse proxy or an SSH tunnel:

```bash
ssh -N -L 2455:127.0.0.1:2455 user@your-vps
```

## Data and development

Local data lives in `~/.swissai-lb`. Back up the database **together with `encryption.key`**; losing that key makes saved upstream credentials unreadable. Never commit keys, database files, bootstrap tokens or `.env.local`.

- [Operations and backup guidance](openspec/specs/swissai-key-pool/context.md)
- [Settings reference](openspec/specs/configuration-tiers/reference.md) · [Login recovery](openspec/specs/admin-auth/ops.md)
- Development: `make ci` for local checks; `make ci-extended` for integration/database/container checks.

Based on [codex-lb](https://github.com/Soju06/codex-lb).
