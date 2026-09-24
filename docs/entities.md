# Entities and data

Codex-LB Rates creates Home Assistant devices and sensors from the quota windows the provider actually reports.

The integration intentionally uses **remaining percentage** as the primary value. If a sensor is `25%`, about one quarter of that quota window remains.

## Account devices

Each monitored account becomes a device named from the first available value:

1. provider display name;
2. email address;
3. account ID.

The device model is shown as **ChatGPT / Codex account**.

### Core account sensors

These sensors are created when the relevant provider data exists.

| Sensor | Codex-LB | ChatGPT / CLI | State |
|---|:---:|:---:|---|
| Primary remaining | Yes | Yes | Remaining % |
| Secondary remaining | Yes | Yes | Remaining % |
| Monthly remaining | When reported | No | Remaining % |
| Primary used | Optional | Optional | Used % (off by default) |
| Secondary used | Optional | Optional | Used % (off by default) |
| Monthly used | Optional when reported | No | Used % (off by default) |
| Primary reset | When reported | When reported | Countdown or local date/time |
| Secondary reset | When reported | When reported | Countdown or local date/time |
| Monthly reset | When reported | No | Countdown or local date/time |
| Status | Yes | Yes | Normalized account status |
| Reset credits | When reported | When reported | Available reset-credit count |
| Spark primary remaining/reset | When reported | No | Remaining % / reset |
| Spark secondary remaining/reset | When reported | No | Remaining % / reset |
| Spark primary/secondary used | Optional when reported | No | Used % (off by default) |

The internal keys still use names such as `remaining_5h` and `remaining_weekly` for compatibility, but the **display name can be corrected from the provider-reported window duration**.

For example:

- about 300 minutes → **5h**;
- about 1 day → **Daily**;
- about 7 days → **Weekly**;
- about 30 days → **Monthly**;
- about 1 year → **Annual**.

If the provider does not supply a window duration, the existing fallback name is used.

> [!TIP]
> Friendly names can change when better duration metadata becomes available. Use the entity ID from **Developer tools → States** in automations rather than matching on the friendly name.

## Remaining-percentage attributes

Account remaining sensors can include:

| Attribute | Meaning |
|---|---|
| `account_id` | Provider account identifier |
| `email` | Account email when available |
| `used_percent` | Provider-reported used percentage when available |
| `window_minutes` | Duration reported for that quota window |
| `quota_model` | Present on Spark sensors; currently `gpt-5.3-codex-spark` |

A provider can report a remaining value without every optional attribute.

## Optional used-% sensors

Used-% sensors are **off by default**. Enable them under the integration's **Configure** options (`used_percent_sensors`).

When enabled, the integration adds used-percentage entities for the same quota windows that already have remaining-% sensors (account devices, and Codex-LB pool aggregates when those windows have samples). Remaining % stays the primary dashboard and automation target; the quota warning blueprint is unchanged.

Account used sensors can include:

| Attribute | Meaning |
|---|---|
| `account_id` | Provider account identifier |
| `email` | Account email when available |
| `remaining_percent` | Remaining percentage for the same window when available |
| `window_minutes` | Duration reported for that quota window |
| `quota_model` | Present on Spark sensors; currently `gpt-5.3-codex-spark` |

## Reset sensors

Reset sensors support two display modes:

- **Countdown** — values such as `4h` or `2d 04h`;
- **Absolute** — a local Home Assistant time such as `2026-09-20 18:30`.

Change this under **Settings → Devices & services → Codex-LB Rates → Configure**.

The display format does not remove the exact timestamp. When a reset time is known, attributes include:

| Attribute | Meaning |
|---|---|
| `resets_at` | Exact ISO-8601 provider reset timestamp |
| `reset_timezone` | Home Assistant timezone used for local display |
| `account_id` | Provider account identifier |
| `email` | Account email when available |

Use `resets_at` when another automation or template needs the machine-readable timestamp.

## Status sensor

The integration normalizes account status into these states:

| State | UI meaning |
|---|---|
| `active` | Ready |
| `rate_limited` | Temporarily rate limited |
| `quota_exceeded` | Quota exhausted |
| `paused` | Paused |
| `reauth_required` | Sign-in required |
| `deactivated` | Deactivated |
| `unknown` | Unknown or unrecognized status |

The original provider value is retained in the `raw_status` attribute.

When Codex-LB reports `additionalQuotas`, the status sensor also includes an `additional_quotas` attribute (always, not only when rich sensors are enabled): a list of structured rows (Spark and any other gated quotas) with keys, labels, routing policy, and primary/secondary window used % / reset / duration.

## Reset credits

When the provider reports reset credits, the integration exposes a **Reset credits** sensor.

Its state is the available count. Codex-LB can also provide an `expires_at` attribute.

## Rich diagnostic sensors

Rich sensors are **off by default**. Enable them under the integration's **Configure** options.

When the provider supplies the values, they add:

- **Plan**;
- **Credits balance**;
- **Last refresh**;
- **Request count** (Codex-LB `requestUsage` totals: state is request count; attributes can include `total_tokens`, `cached_input_tokens`, and `total_cost_usd`).

These are diagnostic entities and may be absent when the upstream API does not provide the corresponding value.

For ChatGPT / CLI accounts, **Last refresh** uses a timestamp from the usage payload when present; otherwise it falls back to the time of the last successful poll.

## Codex-LB pool device

Codex-LB mode can create a separate **Codex-LB pool** device.

It contains aggregate remaining-percentage sensors for every quota window with at least one measured account:

- primary;
- secondary;
- monthly;
- Spark primary;
- Spark secondary.

When used-% sensors are enabled, matching aggregate **used** sensors are created for those same windows (derived from the remaining pool aggregates).

### How pool remaining is calculated

The aggregate includes **every account with a measured value**, including accounts at `0%`. It is not limited to accounts whose status is `active`.

For normal quota windows, the integration uses Codex-LB's reported capacity credits as weights when **every reporting account has a valid positive capacity**.

If one or more reporting accounts are missing usable capacity data, the whole window falls back to **equal weighting** rather than mixing capacity-weighted and unweighted accounts.

Spark windows use the corresponding account plan capacities as relative weights.

### Pool attributes

Pool remaining sensors can include:

| Attribute | Meaning |
|---|---|
| `min` / `max` | Lowest/highest remaining percentage among reporting accounts |
| `account_count` | Total accounts in the Codex-LB snapshot |
| `active_count` | Accounts whose normalized status is active |
| `sample_count` | Accounts that actually reported this quota window |
| `missing_quota_count` | Accounts in the snapshot without a value for this window |
| `window_minutes` | Shared duration when reporting accounts agree |
| `by_minutes` | Per-duration aggregate values when accounts report mixed window lengths |
| `weighting_method` | Capacity/equal-weight method used |
| `missing_weight_count` | Reporting accounts without usable capacity weights |
| `capacity_credits` | Sum of capacity weights when normal capacity weighting is available |
| `quota_model` | Spark model identifier on Spark pool sensors |

When accounts report different durations for the same logical slot, the pool sensor keeps all measured accounts and exposes the split in `by_minutes` rather than silently dropping one account type.

## Optional windows appearing or disappearing

A successful provider poll is treated as the current source of truth for supported windows.

If a monthly or Spark window is no longer returned:

- the corresponding active entity can be removed;
- if the user had explicitly disabled or hidden an optional window entity, the integration preserves that preference/history where possible;
- the entity can return if the provider later reports the window again.

A failed poll does not trigger the same cleanup path.

## Finding your entity IDs

Open **Developer tools → States** and search for a device/account name or `codex`.

Do not assume the example IDs in this documentation exactly match yours. Home Assistant generates entity IDs from device/entity names and preserves registry IDs across normal updates.

Next: [Dashboard examples](dashboard.md) or [Quota alert automations](automations.md).
