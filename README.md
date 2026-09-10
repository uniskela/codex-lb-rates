# Codex Rates (Home Assistant)

Home Assistant custom integration that shows **Codex 5-hour** and **weekly** quota remaining on your dashboard.

Supports:

- **[Codex-LB](https://github.com/soju06/codex-lb)** — all pooled accounts + pool-wide average gauges
- **ChatGPT / Codex CLI** — OAuth (device code or paste callback), `auth.json`, or advanced tokens

## Install (HACS)

1. Add [`https://github.com/uniskela/codex-rates`](https://github.com/uniskela/codex-rates) as a **custom repository** (Integration) in HACS, or copy `custom_components/codex_rates` into your HA `config/custom_components/` folder.
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → Codex Rates**.

## Codex-LB setup

1. Choose **Codex-LB**.
2. Enter your Codex-LB base URL (e.g. `http://192.168.1.10:2455`).
3. Enter dashboard password (leave empty if dashboard auth is disabled).
4. Optionally enter a TOTP secret if 2FA is enabled.

You get:

- Per-account sensors: 5h remaining %, weekly remaining %, reset times, status
- Pool device: **All accounts 5h remaining %** and **All accounts weekly remaining %** (mean of active accounts)

> Codex-LB **API keys cannot** read account quotas — the accounts API requires dashboard session auth.

## ChatGPT / Codex CLI setup

Pick one auth method:

| Method | Best for |
|--------|----------|
| **Device code** | HA in Docker / remote (recommended) |
| **Browser + paste callback** | Same OAuth as Codex-LB; paste the full `localhost:1455` callback URL |
| **auth.json** | Bind-mount `~/.codex/auth.json` into HA and point at the path |
| **Paste tokens** | Advanced / last resort |

Tokens are stored in the config entry (not YAML). Refresh tokens are used automatically when access expires.

## Options

- **Poll interval** (default 60s, minimum 30s)
- **Enable rich sensors** — plan type, credits balance, last refresh

## Lovelace example

```yaml
type: gauge
entity: sensor.codex_lb_pool_all_accounts_5h_remaining
name: Codex pool 5h
min: 0
max: 100
severity: 30
severity: 70
```

```yaml
type: entities
entities:
  - entity: sensor.a_example_com_5h_remaining
  - entity: sensor.a_example_com_weekly_remaining
```

(Entity IDs depend on account names; check **Developer tools → States**.)

## Security

- Never put access tokens or dashboard passwords in `configuration.yaml`.
- Diagnostics redact secrets.
- Password / TOTP / token fields use HA password inputs.
- Codex-LB uses a **private** HTTP session so dashboard cookies are not shared with other integrations.
- See [SECURITY.md](SECURITY.md) for reporting guidance.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

## License

MIT
