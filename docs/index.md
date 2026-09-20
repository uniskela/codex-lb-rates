# Codex-LB Rates documentation

Codex-LB Rates exposes Codex quota information as normal Home Assistant devices and sensors. It can monitor either a **Codex-LB account pool** or an individual **ChatGPT / Codex CLI account**.

The integration is designed around **remaining quota**, not quota already used. A sensor at `20%` means roughly 20% of that quota window remains.

## Start here

If this is your first time installing the integration:

1. [Install Codex-LB Rates](installation.md).
2. [Configure your provider](configuration.md).
3. [Understand the entities Home Assistant creates](entities.md).
4. Optionally build a [dashboard](dashboard.md) or set up [quota alerts](automations.md).

If you already use the integration, see [upgrading](upgrading.md) before changing versions or re-importing the alert blueprint.

## Choose a mode

| Mode | Use it when | What you get |
|---|---|---|
| **Codex-LB** | You run a Codex-LB server with one or more accounts | Per-account devices, pool-wide remaining sensors, optional monthly and Spark quota windows when Codex-LB reports them |
| **ChatGPT / Codex CLI** | You want to monitor one ChatGPT account directly | Per-account primary/secondary quota windows, reset times, reset credits, status, and optional diagnostic sensors |

You can add the integration more than once for different ChatGPT accounts. A Codex-LB host is configured once and exposes the accounts reported by that server.

## What Home Assistant shows

Each account becomes a Home Assistant device. Depending on the provider data, that device can contain:

- remaining quota percentages;
- reset countdowns or local reset date/time values;
- account status;
- reset credits;
- optional plan, credit balance, and last-refresh diagnostics;
- Codex-LB-only monthly and GPT-5.3-Codex-Spark quota sensors when those windows are actually reported.

Codex-LB mode also creates a **Codex-LB pool** device with capacity-weighted remaining percentages across reporting accounts.

Quota window names are based on the duration reported by the provider when that information is available. For example, a provider-reported 24-hour secondary window can appear as **Daily remaining** instead of being incorrectly labelled Weekly.

## Important behaviour

> [!NOTE]
> Optional quota windows are created only when the provider reports them. A missing monthly or Spark sensor usually means that account/provider did not return that quota window; it does not automatically mean the integration is broken.

> [!TIP]
> Automations should normally use the actual entity IDs shown in **Developer tools → States**. Friendly names can change when the provider reports a more accurate quota-window duration.

## Documentation map

| Guide | Use it for |
|---|---|
| [Installation](installation.md) | HACS, manual installation, first setup |
| [Configuration](configuration.md) | Codex-LB login modes, ChatGPT authentication, integration options |
| [Entities and data](entities.md) | Sensors, attributes, pool weighting, dynamic window names |
| [Dashboard examples](dashboard.md) | Practical Lovelace cards for quota and resets |
| [Quota alert automations](automations.md) | Low/exceeded/refreshed notifications without alert spam |
| [Upgrading](upgrading.md) | Integration updates vs blueprint updates |
| [Troubleshooting](troubleshooting.md) | Missing sensors, stale data, authentication, diagnostics |
| [Releases](releases.md) | Maintainer release/versioning process |

## Security and privacy

Credentials are stored in the Home Assistant config entry rather than `configuration.yaml`, and integration diagnostics redact passwords and OAuth tokens. Diagnostics can still contain account identifiers, email addresses, quota values, and timing information, so review a diagnostics file before sharing it publicly.

See [SECURITY.md](../SECURITY.md) for vulnerability reporting.
