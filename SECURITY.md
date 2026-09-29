# Security Policy

## Reporting

If you find a security issue in Codex-LB Rates, open a **private** GitHub security advisory on [uniskela/codex-lb-rates](https://github.com/uniskela/codex-lb-rates) or email the maintainer. Do not file a public issue with live tokens, passwords, or `auth.json` contents.

## What this integration stores

- **Codex-LB:** dashboard password, optional TOTP secret, and optional Cloudflare Access service token Client ID/Secret in the Home Assistant config entry.
- **ChatGPT / Codex CLI:** access / refresh / id tokens (and optional path to `auth.json`) in the config entry.

Secrets are never written to `configuration.yaml` by this integration. Diagnostics redact passwords, TOTP secrets, Cloudflare Access client secrets, and tokens.

## Operator guidance

- Prefer OAuth (device code / paste-callback) over pasting long-lived tokens when possible.
- Point Codex-LB at a trusted URL on your LAN or VPN when possible; treat the base URL like any other local service endpoint.
- If Codex-LB is exposed via Cloudflare Tunnel + Access, use a **Service Auth** service token in this integration rather than sharing a browser `CF_Authorization` cookie. Scope that token tightly to the Codex-LB Access app.
- Keep Home Assistant and Codex-LB off the public internet unless behind strong auth.
- Do not commit `auth.json`, session cookies, Access secrets, or HA `.storage` config entries to git.
