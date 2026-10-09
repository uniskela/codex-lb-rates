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

On a recent Home Assistant frontend (≈2023.5+), the card supports the **Visual editor** via `getConfigElement` (preferred) and `getConfigForm` (built-in `ha-form` fallback):

| Field | Config key | Notes |
|---|---|---|
| Title | `title` | Optional card heading |
| Primary remaining entity | `entity` | Hero remaining-% sensor |
| Primary name override | `name` | Optional label for the primary entity only |
| Additional remaining entities | `entities` | Multi-select of extra remaining-% sensors (string entity IDs) |
| Green / yellow thresholds | `green` / `yellow` | Colour bands; defaults `50` / `20` |

Form-safe example (string entity IDs only — round-trips through the visual editor):

```yaml
type: custom:codex-rates-card
title: Codex pool
entity: sensor.codex_lb_pool_all_accounts_5h_remaining
name: Pool primary
entities:
  - sensor.codex_lb_pool_all_accounts_weekly_remaining
green: 50
yellow: 20
```

### YAML-only advanced

Object-form `entities` rows (`{ entity, name? }`, with or without a custom `name`) remain fully supported at runtime. When any `entities` item is an object, the visual editor stays disabled so a GUI save cannot rewrite that list — edit those cards in the **Code editor** (YAML) instead.

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
- Top-level `name` (primary only) is available in both the visual form and YAML; per-row names under `entities` are YAML-only.

Hard-refresh the browser (or clear the dashboard cache) after an integration update if an older card bundle is still cached.

If the editor still says **Visual editor not supported** after updating to a release that includes it:

1. Confirm the integration is on **0.8.0+** (or a build that includes the visual editor).
2. Restart Home Assistant, then hard-refresh the dashboard (Ctrl/Cmd+Shift+R).
3. Open the browser console — you should see `Codex-LB Rates card v1.1.1` (or newer).
4. Under **Settings → Dashboards → Resources**, confirm the module URL is `/codex_rates/codex-rates-card.js?v=…` (a changing `?v=` digest). If you added the resource manually without `?v=`, append a new query (for example `?v=2`) once so the browser drops the stale module.

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
