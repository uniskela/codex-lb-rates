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
| Theme | `theme` | Installed Home Assistant theme; leave empty to inherit the view/dashboard theme |
| Reset display | `reset_display` | `countdown` (default), `absolute`, or `hidden`; applies to every row |
| Primary entity | `entity` | Hero remaining-% sensor |
| Label | `name` | Replaces the primary entity name on the card. Blank keeps the entity name |
| Additional entity | `entities` | Extra remaining-% rows. Each row can set its own label |
| Green / yellow thresholds | `green` / `yellow` | Colour bands; defaults `50` / `20` |

Form-safe example (string entity IDs only — round-trips through the visual editor):

```yaml
type: custom:codex-rates-card
title: Codex pool
entity: sensor.codex_lb_pool_all_accounts_5h_remaining
name: Pool primary
reset_display: countdown
entities:
  - sensor.codex_lb_pool_all_accounts_weekly_remaining
green: 50
yellow: 20
```

### Labels

The visual editor lists installed sensor entities for the primary row and each additional row. **Label** replaces the entity name on the card (the “Codex-LB pool All accounts …” text). Leave a label blank to keep the entity’s name. A label on an additional row is saved as `{ entity, name }`; a blank label stays a plain entity ID.

Object-form rows still load in the visual editor. The built-in form fallback, used only when the card editor element is unavailable, still refuses object rows so it cannot flatten them.

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
- Extra `entities` rows show additional remaining-% sensors (other pool windows or accounts) and their reset timing, including weekly, monthly, and Spark windows when reported.
- Optional `green` / `yellow` thresholds default to `50` / `20` (same “plenty / getting low / little left” bands as the gauge examples below).
- The primary pool shows measured-account counts and weighting, plus incomplete reset coverage when applicable.
- Tap/click the large quota or an extra row to open that entity's **More info** dialog. Keyboard users can Tab to a quota and press Enter or Space.
- Top-level `name` and per-row `entities` labels are editable in the visual editor and in YAML.

### BREAKING CHANGE: pool card display

After updating, existing custom-card configurations show reset timing in place of the primary pool's visible `min` / `max` values. Users who relied on those values in the card will need to access them elsewhere. The sensor attributes, quota values, and entity IDs are retained.

To access `min` / `max`, tap the pool quota to open its **More info** dialog, or display those attributes using attribute rows in a standard Entities card. Setting `reset_display: hidden` hides reset timing; it does not restore the old min/max display.

### Reset countdowns and times

Your existing card configuration automatically shows minute-resolution reset countdowns after updating the integration:

- Account: **Resets in 4h 07m**.
- Weekly account: **Resets in 3d 02h 05m**.
- Pool: **Next reset in 4h 07m** — the earliest upcoming reset among measured accounts with known times. A pool does not reset all accounts together.

Choose **Reset date/time** in the visual editor, or set `reset_display: absolute`, to show the date and time using your frontend language, 12/24-hour preference, and time zone preference (Home Assistant's configured zone, or your browser's local zone). The card setting is independent of the integration's reset-sensor display option. Set `reset_display: hidden` to omit reset lines.

Countdowns round up to the next minute and update every minute while the card is attached. When a timestamp passes, the card says **Reset due · awaiting update** until new provider data arrives; it does not assume the percentage has refilled. Missing timestamps show **Reset time unavailable**, and unavailable quota sensors show **Unavailable**.

The card reads `resets_at` directly from account remaining sensors and `next_reset_at` from pool sensors. It also works with other remaining-% sensors that provide these attributes; it does not guess a sibling entity ID. Restart Home Assistant after the integration update so the new attributes are published.

### Themes and frosted glass styling

The **Theme** dropdown lists themes installed in Home Assistant. Leave it empty to inherit the surrounding view/dashboard theme. An explicit theme applies its variables, including its active light/dark mode, only to this card:

```yaml
type: custom:codex-rates-card
title: Codex remaining
theme: Frosted Glass
entity: sensor.codex_lb_pool_all_accounts_5h_remaining
entities:
  - sensor.codex_lb_pool_all_accounts_weekly_remaining
reset_display: countdown
```

The card uses Home Assistant's `ha-card` for its background, border, radius, shadow, and backdrop filter. It preserves that container during quota updates so external card styling can remain attached.

If your other cards use individual `card_mod` gradients and blur, selecting the view theme alone will not reproduce those per-card styles. With [card-mod](https://github.com/thomasloven/lovelace-card-mod) installed, add the same treatment to this card:

```yaml
card_mod:
  style: |
    ha-card {
      background: linear-gradient(135deg, rgba(24, 28, 36, 0.72), rgba(18, 22, 30, 0.58));
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      border-radius: 18px;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22);
      --primary-text-color: rgba(255, 255, 255, 0.98);
      --secondary-text-color: rgba(255, 255, 255, 0.68);
    }
```

This is an optional dashboard styling dependency; the integration does not install card-mod or a theme for you.

Hard-refresh the browser (or clear the dashboard cache) after an integration update if an older card bundle is still cached.

If the editor still says **Visual editor not supported** after updating to a release that includes it:

1. Confirm the integration is on **0.8.0+** (or a build that includes the visual editor).
2. Restart Home Assistant, then hard-refresh the dashboard (Ctrl/Cmd+Shift+R).
3. Open the browser console — you should see `Codex-LB Rates card v1.2.0` (or newer).
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
