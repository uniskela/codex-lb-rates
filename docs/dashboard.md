# Dashboard examples

Codex-LB Rates uses normal Home Assistant sensors, so you can build dashboards with standard cards.

> [!IMPORTANT]
> Replace every example entity ID below with the real ID from **Developer tools → States**. Account names and generated IDs vary by installation.

## Simple account card

An Entities card is a good starting point because it can show quota, reset, and status together.

```yaml
type: entities
title: Codex quota
entities:
  - entity: sensor.my_account_5h_remaining
    name: Primary remaining
  - entity: sensor.my_account_weekly_remaining
    name: Secondary remaining
  - entity: sensor.my_account_5h_resets
    name: Primary resets
  - entity: sensor.my_account_weekly_resets
    name: Secondary resets
  - entity: sensor.my_account_status
    name: Account status
```

If your provider reports different window durations, Home Assistant may display names such as **Daily remaining** or **Annual remaining** instead. The entity IDs in an existing registry normally remain the IDs you already use.

## Pool gauges

For Codex-LB, pool remaining sensors are useful as at-a-glance gauges.

```yaml
type: gauge
entity: sensor.codex_lb_pool_all_accounts_5h_remaining
name: Pool primary quota
min: 0
max: 100
needle: true
severity:
  green: 50
  yellow: 20
  red: 0
```

For a remaining-percentage sensor:

- green means plenty remains;
- yellow means quota is getting low;
- red means little remains.

Create another gauge for your secondary or monthly pool entity if those sensors exist.

## Compact tile cards

A grid of Tile cards works well on mobile.

```yaml
type: grid
columns: 2
square: false
cards:
  - type: tile
    entity: sensor.my_account_5h_remaining
    name: Primary
  - type: tile
    entity: sensor.my_account_weekly_remaining
    name: Secondary
  - type: tile
    entity: sensor.my_account_5h_resets
    name: Primary reset
  - type: tile
    entity: sensor.my_account_status
    name: Status
```

## Show reset timestamp attributes

Reset sensors are intentionally human-readable. Their exact ISO reset timestamp is stored in the `resets_at` attribute.

If you need a separate template sensor or card that uses that timestamp, first inspect the entity in **Developer tools → States** and confirm that `resets_at` exists for the current provider response.

For most dashboards, the built-in reset sensor is simpler:

- **Countdown** mode for “how long is left?”;
- **Absolute** mode for “what local time does it reset?”.

Change the display under the integration's **Configure** options.

## Pool health/details card

Pool sensor attributes can help diagnose why an aggregate looks different from a simple average.

Add a pool entity to an Entities card, then open its **More info** dialog to inspect:

- `sample_count`;
- `missing_quota_count`;
- `weighting_method`;
- `missing_weight_count`;
- `capacity_credits` when available;
- `by_minutes` when accounts report different window lengths.

A pool percentage is therefore best treated as “the integration's aggregate remaining quota across reporting accounts”, not as a raw arithmetic mean.

## Missing cards or unavailable entities

If an example sensor does not exist, do not create a template to fake it. First check whether the provider actually reports that quota window.

See [Entities and data](entities.md) and [Troubleshooting](troubleshooting.md).

## Notifications

Dashboard cards do not need to continuously watch thresholds. For one-shot low/exceeded/refreshed notifications with hysteresis, use the [quota alert blueprint](automations.md).
