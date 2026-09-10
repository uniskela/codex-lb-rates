# Codex-LB Rates

Home Assistant integration for **Codex 5-hour** and **weekly** quota remaining—built first for [Codex-LB](https://github.com/soju06/codex-lb) account pools, with a ChatGPT / Codex CLI mode for single accounts.

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/uniskela/codex-lb-rates/actions/workflows/validate.yml/badge.svg)](https://github.com/uniskela/codex-lb-rates/actions/workflows/validate.yml)
[![CodeQL](https://img.shields.io/badge/CodeQL-enabled-brightgreen)](https://github.com/uniskela/codex-lb-rates/security/code-scanning)
[![License](https://img.shields.io/github/license/uniskela/codex-lb-rates)](LICENSE)

## Features

- **Codex-LB pool monitoring** — every pooled account as its own device, plus pool gauges (mean remaining % for 5h / weekly / monthly across active accounts)
- **Per-account sensors** — remaining %, `Xd XXh` reset countdowns, reset credits, status (rich sensors optional)
- **ChatGPT / Codex CLI** — device-code OAuth, browser paste-callback, `auth.json`, or advanced tokens
- Secrets stay in the config entry (password inputs, redacted diagnostics)

## Install (HACS)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=uniskela&repository=codex-lb-rates&category=integration)

1. Click the badge above, **or** in HACS add custom repository `https://github.com/uniskela/codex-lb-rates` (type: Integration), **or** copy `custom_components/codex_rates` into your HA `config/custom_components/` folder.
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → Codex-LB Rates**.

## Codex-LB setup

1. Choose **Codex-LB**.
2. Enter your Codex-LB base URL (e.g. `http://192.168.1.10:2455`).
3. Pick **Login mode**:
   - **Admin** — dashboard password (± optional TOTP)
   - **Guest** — read-only session when the server enables guest access (password only if the server requires one)
4. Leave password empty if dashboard auth is disabled.

You get:

- Per-account sensors: 5h / weekly / monthly remaining %, reset countdowns (`Xd XXh` with `resets_at` attribute), **reset credits**, status
- Optional rich sensors: plan, credits balance, last refresh
- Pool device: mean remaining % for 5h, weekly, and monthly across active accounts (attributes include min/max/counts; when window lengths differ, mean prefers the most common duration and exposes `by_minutes`)
- Stale account devices from older identifier formats are pruned automatically after upgrade/reload

> Codex-LB **API keys cannot** read account quotas — the accounts API requires dashboard session auth.

## ChatGPT / Codex CLI setup

Use this when you are not running Codex-LB and still want 5h / weekly / **reset credits** sensors for one ChatGPT account. Monthly sensors are Codex-LB only (ChatGPT usage has no monthly window).

| Method | Best for |
|--------|----------|
| **Device code** | HA in Docker / remote (recommended) |
| **Browser + paste callback** | Paste the full `localhost:1455` callback URL after sign-in |
| **auth.json** | Bind-mount `~/.codex/auth.json` into HA and point at the path |
| **Paste tokens** | Advanced / last resort |

Tokens are stored in the config entry (not YAML). Refresh tokens renew access automatically when possible. Add the integration again for another account. Reload the integration after upgrading so reset sensors switch from fuzzy timestamps to `Xd XXh` countdowns and orphan devices are cleaned up.

## Options

- **Poll interval** (default 60s, minimum 30s)
- **Enable rich sensors** — plan type, credits balance, last refresh

## Lovelace example

```yaml
type: gauge
entity: sensor.codex_lb_pool_all_accounts_5h_remaining
name: Codex-LB pool 5h
min: 0
max: 100
severity: 30
severity: 70
```

```yaml
type: entities
title: Codex-LB accounts
entities:
  - entity: sensor.a_example_com_5h_remaining
  - entity: sensor.a_example_com_weekly_remaining
```

(Entity IDs depend on account names; check **Developer tools → States**.)

## Quota warnings

Ship a Home Assistant automation blueprint that warns once when a **remaining %** sensor drops to or below a threshold (default **20%** left), then rearms after remaining recovers by a margin (default **5** pp). Uses a persistent `input_boolean` helper so you are not spammed while quota stays low.

1. Create a **Toggle** helper (**Settings → Devices & services → Helpers**) with no forced initial value — one helper per automation.
2. Copy [`blueprints/automation/codex_rates/quota_warning.yaml`](blueprints/automation/codex_rates/quota_warning.yaml) into `config/blueprints/automation/codex_rates/` on your HA instance (or import the raw file URL from the release you installed).
3. **Create automation → Use blueprint** and pick a remaining-% sensor (pool or account), threshold, helper, and notify/script action.

Works for pool gauges and per-account 5h / weekly remaining sensors. Sensors are **remaining**, not used — threshold 20 means warn when ≤20% is left.

More detail: [docs/automations.md](docs/automations.md).

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

Releases are automated with [Release Please](https://github.com/googleapis/release-please). Prefer [Conventional Commits](https://www.conventionalcommits.org/) on `main` (`feat:`, `fix:`, etc.). After merge, Release Please opens a release PR that bumps `version.txt`, `custom_components/codex_rates/manifest.json`, and `CHANGELOG.md`, then tags/publishes the GitHub release when that PR merges.

See [AGENTS.md](AGENTS.md) (agent workflow, including `Release-As` for a specific SemVer) and [docs/releases.md](docs/releases.md).

## License

MIT
