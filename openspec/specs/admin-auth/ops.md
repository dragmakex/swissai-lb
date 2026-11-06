# Dashboard login recovery

Owner: [admin-auth specification](spec.md). For SwissAI bootstrap/network policy, see [SwissAI context](../swissai-key-pool/context.md).

These commands are for an operator who controls the configured application database. They bypass dashboard login by design, make no identity-provider network call, and record a critical `break_glass_cli_used` audit event. Protect host/container access accordingly. Use the same data-directory/database configuration as the running service; do not point recovery at a new empty database.

## Bootstrap and ordinary sign-in

Set your initial dashboard password in the browser. Remote setup requires the configured `SWISSAI_LB_DASHBOARD_BOOTSTRAP_TOKEN` or the generated `<data_dir>/bootstrap.token`; the generated secret is not printed in server logs. Dashboard authentication is separate from local inference-client authentication.

The default local sign-in policy is `enabled`. Advanced `admins_only` and `break_glass_only` policies remain available. Tightening policy requires an active emergency administrator with a local password and enrolled two-factor authentication; a designation alone is insufficient. Save its username and `/login?local=1` URL in your password manager before tightening policy. An emergency session always requires its second factor and is critically audited. The API prevents removing the last qualifying emergency account while the policy is restricted.

## Host commands

From a source checkout:

```bash
uv run swissai-lb admin local-login enable
uv run swissai-lb admin reset-password <username>
uv run swissai-lb admin disable-provider <provider-id>
uv run swissai-lb admin reset-login-policy
```

For the standard Compose service, use `docker compose exec server python -m app.cli admin ...` with the same subcommand. Password reset requires an interactive terminal and prompts twice; never put a password in arguments or shell history.

- `local-login enable` restores the local password policy without a qualifying-account check.
- `reset-password <username>` changes the password and signs the account out everywhere. It does not reactivate disabled accounts.
- `disable-provider <id>` turns off that provider; an unknown ID lists configured providers without changing them.
- `reset-login-policy` enables local login and disables company providers while retaining the password provider. It asks for confirmation; `--yes` is for deliberate non-interactive recovery.

A running server observes these changes within about five seconds; no restart is normally needed. Commands refuse an unmigrated database rather than creating an unrelated installation.

## Lost second factor or unavailable provider

First try the emergency account at `/login?local=1`. If another administrator can sign in, use Settings → Access → People to reset a lost factor; restricted policy still protects the last qualifying emergency account.

If nobody can sign in, reopen local login on the host. For an administrator whose second factor is lost:

```bash
uv run swissai-lb admin reset-password <username> --clear-two-factor
```

The command also reopens local sign-in in the same transaction **only if** clearing the factor would leave nobody the current policy admits. The install-wide two-factor requirement is unchanged. Enrol a new authenticator before re-tightening policy.

If provider redirects still prevent login, deliberately disable that provider or run `admin reset-login-policy`, then repair/re-enable the provider through the dashboard. Reopening local login is a recovery action, not a reason to weaken reverse-proxy trust or expose the application publicly.
