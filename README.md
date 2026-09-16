# Codex-LB Rates

Home Assistant integration for **Codex 5-hour** and **weekly** quota remaining—built first for [Codex-LB](https://github.com/soju06/codex-lb) account pools, with a ChatGPT / Codex CLI mode for single accounts.

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/uniskela/codex-lb-rates/actions/workflows/validate.yml/badge.svg)](https://github.com/uniskela/codex-lb-rates/actions/workflows/validate.yml)
[![CodeQL](https://img.shields.io/badge/CodeQL-enabled-brightgreen)](https://github.com/uniskela/codex-lb-rates/security/code-scanning)
[![License](https://img.shields.io/github/license/uniskela/codex-lb-rates)](LICENSE)

## Features

- **Codex-LB pool monitoring** — every pooled account as its own device, plus pool gauges (capacity-weighted remaining % for 5h / weekly / monthly across all accounts)
- **Per-account sensors** — remaining %, reset countdowns or absolute local dates (configurable), reset credits, status (rich sensors optional)
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

- Per-account sensors: 5h / weekly / monthly remaining %, reset sensors as `Xd XXh` countdowns by default (or absolute local dates via **Configure** → Reset sensor display), with the exact ISO timestamp in `resets_at`, **reset credits**, status
- Optional rich sensors: plan type, credits balance, last refresh
- Pool device: capacity-weighted remaining % for 5h, weekly, and monthly across all accounts, including exhausted accounts at 0%. Weights come from Codex-LB’s `capacityCreditsPrimary`, `capacityCreditsSecondary`, and `capacityCreditsMonthly`, so account plans contribute in proportion to their quota capacity.
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

Tokens are stored in the config entry (not YAML). Refresh tokens renew access automatically when possible. Add the integration again for another account. Restart Home Assistant after upgrading the Python integration. Existing entity IDs remain stable; reset sensors default to `Xd XXh` countdowns and can switch to absolute `YYYY-MM-DD HH:MM` in Home Assistant’s timezone via options, while `resets_at` always retains the machine-readable timestamp. Status codes remain stable for automations and receive readable labels and icons in the UI.

## Options

- **Poll interval** (default 60s, minimum 30s)
- **Enable rich sensors** — plan type, credits balance, last refresh
- **Reset sensor display** — `countdown` (`Xd XXh`, default) or `absolute` (local date/time)

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

## Quota alerts

Current blueprint: **Codex-LB Rates quota alerts v2.0.0**. The blueprint version is independent of the integration version and is shown in the blueprint name/description so an older imported copy is easy to identify.

The blueprint alerts on **low**, **exceeded**, and **refreshed** remaining-% levels across one or more pool/account sensors. It is event-driven: selected sensors are checked when their percentage state changes, all selected sensors are checked once when Home Assistant starts or automations reload, and there is no five-minute polling loop. Thresholds are evaluated inside the automation rather than using threshold-only triggers, which preserves the blueprint's exact ≤/≥ and hysteresis behaviour.

[![Open your Home Assistant instance and import the Codex-LB Rates quota alert blueprint.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Funiskela%2Fcodex-lb-rates%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fcodex_rates%2Fquota_warning.yaml)

1. Create a **Text** helper: **Settings → Devices & services → Helpers → Create helper → Text**, name it, set max length **255**, and leave its initial value **blank**.
2. Click the import badge above, **or** copy [`blueprints/automation/codex_rates/quota_warning.yaml`](blueprints/automation/codex_rates/quota_warning.yaml) into `config/blueprints/automation/codex_rates/`.
3. **Create automation → Use blueprint**, choose remaining-% sensors, that Text helper, alert levels, and optional Companion phones.

Version 2 can initialize a new helper that reports `unknown`, migrates the old full-entity alert tokens to compact stable tokens, and sends phone notifications through Home Assistant notify entities instead of guessing a `notify.mobile_app_*` action from the device display name.

If you imported an earlier copy, use **Settings → Automations & scenes → Blueprints → ⋮ → Re-import blueprint** to refresh it from its saved source URL. The one-click badge above follows `main`, so re-importing picks up the current blueprint; use a release-tag URL instead if you intentionally want to stay pinned.

Works for pool gauges and per-account remaining sensors. Sensors are **remaining**, not used — low threshold 20 means warn when ≤20% is left (and above the exceeded band). Full setup, migration notes, blueprint changelog, and update instructions: [docs/automations.md](docs/automations.md).

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
