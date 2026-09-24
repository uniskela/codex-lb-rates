# Dashboard examples

Codex-LB Rates uses normal Home Assistant sensors, so you can build dashboards with standard cards. It also ships an optional **custom Lovelace card** for pool and remaining-% at a glance.

> [!IMPORTANT]
> Replace every example entity ID below with the real ID from **Developer tools → States**. Account names and generated IDs vary by installation.

## Custom remaining card

The integration packages a Lovelace module at:

`/codex_rates/codex-rates-card.js`

After you install or update the integration and restart Home Assistant, **storage-mode** Lovelace usually registers that module automatically when the integration loads. If the card type is still missing from the UI picker (or you use **YAML-mode** resources), add it once under **Settings → Dashboards → ⋮ → Resources**:

| Field | Value |
|---|---|
| URL | `/codex_rates/codex-rates-card.js` |
| Resource type | **JavaScript module** |

YAML-mode Lovelace cannot be updated by the integration. Add the same URL under your Lovelace `resources:` list (or rely on the frontend module injection that runs when the integration loads), then reload resources / refresh the browser.

### Visual editor

On a recent Home Assistant frontend (≈2023.5+), the card supports the **Visual editor** tab via `getConfigForm`:

| Field | Config key | Notes |
|---|---|---|
| Title | `title` | Optional card heading |
| Primary remaining entity | `entity` | Hero remaining-% sensor |
| Primary name override | `name` | Optional label for the primary entity only |
| Additional remaining entities | `entities` | Multi-select of extra remaining-% sensors (string entity IDs) |
| Green / yellow thresholds | `green` / `yellow` | Colour bands; defaults `50` / `20` |

If an existing card uses **per-row names** in `entities` (`{ entity, name }`), the visual editor stays disabled so a GUI save cannot strip those overrides — edit that shape in the **Code editor** (YAML) instead. Plain string entity lists and a top-level `name` for the primary entity round-trip through the form.

```yaml
type: custom:codex-rates-card
title: Codex pool
entity: sensor.codex_lb_pool_all_accounts_5h_remaining
entities:
  - sensor.codex_lb_pool_all_accounts_weekly_remaining
  - entity: sensor.my_account_5h_remaining
    name: Account primary
```

Behaviour:

- The first entity (`entity`, or the first `entities` item) is the large remaining-% value and progress bar.
- Extra `entities` rows show additional remaining-% sensors (other pool windows or accounts).
- Optional `green` / `yellow` thresholds default to `50` / `20` (same “plenty / getting low / little left” bands as the gauge examples below).
- When the primary entity is a pool sensor, the card surfaces `min` / `max`, `sample_count`, and `weighting_method` when those attributes exist.
- Object-form rows with a custom `name` remain fully supported in YAML; they are the YAML-only advanced option relative to the visual form.

Hard-refresh the browser (or clear the dashboard cache) after an integration update if an older card bundle is still cached.

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
