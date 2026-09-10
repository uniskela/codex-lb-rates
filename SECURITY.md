# Security Policy

## Reporting

If you find a security issue in Codex Rates, open a **private** GitHub security advisory on [uniskela/codex-rates](https://github.com/uniskela/codex-rates) or email the maintainer. Do not file a public issue with live tokens, passwords, or `auth.json` contents.

## What this integration stores

- **Codex-LB:** dashboard password and optional TOTP secret in the Home Assistant config entry.
- **ChatGPT / Codex CLI:** access / refresh / id tokens (and optional path to `auth.json`) in the config entry.

Secrets are never written to `configuration.yaml` by this integration. Diagnostics redact passwords, TOTP secrets, and tokens.

## Operator guidance

- Prefer OAuth (device code / paste-callback) over pasting long-lived tokens when possible.
- Point Codex-LB at a trusted URL on your LAN or VPN; treat the base URL like any other local service endpoint.
- Keep Home Assistant and Codex-LB off the public internet unless behind strong auth.
- Do not commit `auth.json`, session cookies, or HA `.storage` config entries to git.
