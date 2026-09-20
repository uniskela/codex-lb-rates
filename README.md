# Codex-LB Rates

Home Assistant integration for monitoring **Codex quota remaining and reset times** from either a [Codex-LB](https://github.com/soju06/codex-lb) account pool or an individual ChatGPT / Codex CLI account.

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/uniskela/codex-lb-rates/actions/workflows/validate.yml/badge.svg)](https://github.com/uniskela/codex-lb-rates/actions/workflows/validate.yml)
[![CodeQL](https://img.shields.io/badge/CodeQL-enabled-brightgreen)](https://github.com/uniskela/codex-lb-rates/security/code-scanning)
[![License](https://img.shields.io/github/license/uniskela/codex-lb-rates)](LICENSE)

## What it does

- **Codex-LB pools** — one Home Assistant device per account plus pool-wide aggregate quota sensors.
- **ChatGPT / Codex CLI accounts** — direct primary/secondary quota, reset time, reset credits, and status sensors.
- **Provider-aware window names** — display names follow reported durations when available, so a 24-hour window can be shown as Daily instead of being hard-coded as Weekly.
- **Optional quota windows** — monthly and GPT-5.3-Codex-Spark sensors appear only when Codex-LB actually reports them.
- **Capacity-aware pool gauges** — measured accounts, including exhausted accounts at 0%, contribute to the pool aggregate; capacity weighting is used when valid weights are available for every reporting account.
- **Reset display choice** — countdown by default, or local absolute date/time while keeping the exact ISO timestamp in `resets_at`.
- **Optional rich diagnostics** — plan, credit balance, and last refresh.
- **Quota-alert blueprint** — low, exceeded, and refreshed notifications with hysteresis and remembered alert state.

## Install

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=uniskela&repository=codex-lb-rates&category=integration)

1. Install through HACS, or add `https://github.com/uniskela/codex-lb-rates` as a custom **Integration** repository.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Codex-LB Rates**.
4. Choose **Codex-LB** or **ChatGPT / Codex CLI**.

Manual installation is also supported by copying `custom_components/codex_rates` into Home Assistant's `config/custom_components/` directory.

Full instructions: **[Installation](docs/installation.md)**.

## Choose a provider

| Mode | Best for | Authentication |
|---|---|---|
| **Codex-LB** | Multiple accounts behind a Codex-LB server | Admin dashboard session, or read-only Guest session when enabled |
| **ChatGPT / Codex CLI** | Monitoring one ChatGPT account directly | Device code (recommended), browser paste-callback, mounted `auth.json`, or advanced tokens |

Codex-LB API keys cannot read the account quota endpoint used by this integration; use the dashboard/guest session flow.

See **[Configuration](docs/configuration.md)** for the complete setup guide.

## Documentation

| Guide | Covers |
|---|---|
| [Overview](docs/index.md) | How the integration is structured and where to start |
| [Installation](docs/installation.md) | HACS/manual install and first setup |
| [Configuration](docs/configuration.md) | Codex-LB and ChatGPT authentication, options |
| [Entities and data](docs/entities.md) | Sensors, reset attributes, pool weighting, optional windows |
| [Dashboard examples](docs/dashboard.md) | Copyable Lovelace examples |
| [Quota alert automations](docs/automations.md) | Blueprint setup, behaviour, updates, migration |
| [Upgrading](docs/upgrading.md) | Integration updates vs blueprint updates |
| [Troubleshooting](docs/troubleshooting.md) | Authentication, missing sensors, stale data, diagnostics |
| [Releases](docs/releases.md) | Maintainer release/versioning process |

## Quota alerts

Current blueprint: **Codex-LB Rates quota alerts v2.0.0**

It can monitor one or more remaining-% sensors and send one-shot **low**, **exceeded**, and **refreshed** alerts without repeatedly notifying while a sensor remains in the same band.

[![Open your Home Assistant instance and import the Codex-LB Rates quota alert blueprint.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Funiskela%2Fcodex-lb-rates%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fcodex_rates%2Fquota_warning.yaml)

The blueprint requires a Home Assistant **Text helper** for its alert memory and is versioned independently from the integration. Follow **[Quota alert automations](docs/automations.md)** rather than copying the YAML blindly.

## Integration options

Open **Settings → Devices & services → Codex-LB Rates → Configure**.

- **Poll interval** — default 60 seconds; minimum 30 seconds.
- **Enable rich sensors** — plan, credit balance, and last-refresh diagnostics when available.
- **Reset sensor display** — countdown or local absolute date/time.

## Security

- Credentials are stored in the Home Assistant config entry rather than `configuration.yaml`.
- Password, TOTP, access-token, refresh-token, and ID-token fields are redacted from integration diagnostics.
- Codex-LB uses a private HTTP session so its dashboard cookies are not shared with other integrations.
- Diagnostics can still contain account IDs, email addresses, quota values, and timing information; review them before sharing publicly.

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

Releases use [Release Please](https://github.com/googleapis/release-please) and Conventional Commits. Maintainer workflow details live in [AGENTS.md](AGENTS.md) and [docs/releases.md](docs/releases.md).

## License

MIT
