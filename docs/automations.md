# Automations

## Quota alerts blueprint

Blueprint version: **2.0.0**

The quota-alert blueprint notifies once per sensor for **low quota**, **quota exceeded**, and **quota refreshed**, then rearms after recovery so you are not spammed. Select one or more remaining-% sensors (pool and/or individual accounts) in a single automation.

Version 2 is event-driven: it reacts when the **percentage state itself changes**, checks all configured sensors once when Home Assistant starts, and checks them again after automations reload. Attribute-only updates do not trigger it, and there is no periodic timer.

This is **not a threshold-only trigger**. Each actual percentage change runs the lightweight threshold/recovery logic, while the alert is sent only when the configured low, exceeded, refreshed, or rearm conditions are met. Keeping the thresholds in the action logic preserves the blueprint's exact `≤` / `≥` comparisons and hysteresis behaviour.

| Event | Default | Rearms when |
|-------|---------|-------------|
| Low | remaining ≤ **20%** (and above exceeded) | remaining ≥ 20 + **5** pp |
| Exceeded | remaining ≤ **0%** | remaining > 0 + **1** pp |
| Refreshed | remaining ≥ **100%** after a prior low/exceeded | remaining ≤ **90%** |

Built-in delivery:

- **Home Assistant persistent notification** (UI)
- **Companion phone(s)** through Home Assistant notify entities (`notify.send_message`)
- **Additional actions** — optional TTS/scripts/etc. after an alert arms

Phone delivery in v2 deliberately uses the selected Companion device instead of guessing a legacy `notify.mobile_app_<device name>` action. This is more reliable when a Home Assistant device name differs from the Companion registration name. The standard notify-entity action carries the title and message. If you need Companion-specific payload options such as tags, channels, colors, icons, or custom clear-notification behaviour, add them under **Additional actions**.

### Blueprint versions

The blueprint has its own version, independent of the Codex-LB Rates integration version. Home Assistant does not currently provide a native blueprint update entity, so the installed blueprint version is shown directly in its **name and description**.

| Blueprint version | Main changes |
|---|---|
| **2.0.0** | Event-driven percentage changes, startup/reload catch-up checks, no timer polling, empty-helper initialization, compact alert memory with v1 migration, direct notify-entity device targeting, clearer traces, visible blueprint version |
| **1.x** | Legacy full-entity state tokens, periodic five-minute check, inferred `notify.mobile_app_*` action names |

#### Updating an imported blueprint

If you imported the blueprint from GitHub, open **Settings → Automations & scenes → Blueprints**, open the blueprint menu, and choose **Re-import blueprint**. Home Assistant overwrites the imported blueprint from its saved source URL; reload automations if prompted. The blueprint listens for Home Assistant's `automation_reloaded` event so it immediately rechecks all configured quota sensors after a reload instead of waiting for the next percentage change.

For users who want updates when they deliberately re-import, use the `main` branch import below. If you instead import a URL pinned to a release tag, that install intentionally stays on that release until you import a newer tag.

[![Open your Home Assistant instance and import the Codex-LB Rates quota alert blueprint.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Funiskela%2Fcodex-lb-rates%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fcodex_rates%2Fquota_warning.yaml)

Existing v1 multi-sensor automations can keep their selected sensors, Text helper, thresholds, and phones. On the first v2 run, legacy helper tokens such as `sensor.example::low` are recognized and rewritten to compact v2 tokens automatically.

### Why you need a Text helper

Home Assistant automations do not otherwise remember that a warning has already been sent. The **Text helper** stores that alert memory so repeated quota updates inside the same band do not create duplicate alerts.

Version 2 uses compact stable tokens. A helper may look like:

```text
3a19c7de:l 7e0814aa:e
```

The eight hexadecimal characters are a stable hash of the sensor entity ID. The suffix is the event: `l` = low, `e` = exceeded, and `r` = refreshed. This is much smaller than the v1 format, which stored the full entity ID for every flag and could overflow Home Assistant's 255-character Text helper limit in normal multi-account setups.

You do **not** edit these tokens yourself. Create an empty Text helper, select it in the blueprint, and leave it alone. If a newly created helper initially reports `unknown`, v2 initializes it instead of aborting the automation.

### 1. Create the Text helper

1. In Home Assistant open **Settings → Devices & services**.
2. Open the **Helpers** tab.
3. **Create helper → Text**.
4. Fill in:
   - **Name:** e.g. `Codex quota alerts`
   - **Maximum length:** `255`
   - **Initial value:** leave **blank**
5. Submit / create.

You should now have an entity such as `input_text.codex_quota_alerts`.

Use one Text helper **per quota-alert automation**; do not share the same helper between multiple copies of the blueprint. To reset alert memory manually, set the helper value to empty in **Developer tools → States**, or call `input_text.set_value` with an empty value.

### 2. Import the blueprint

Recommended: use the one-click `main` branch import so Home Assistant keeps the GitHub source URL for future **Re-import blueprint** updates.

[![Open your Home Assistant instance and import the Codex-LB Rates quota alert blueprint.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Funiskela%2Fcodex-lb-rates%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fcodex_rates%2Fquota_warning.yaml)

Manual copy is also supported. Copy:

`blueprints/automation/codex_rates/quota_warning.yaml`

into your Home Assistant config as:

`config/blueprints/automation/codex_rates/quota_warning.yaml`

Then reload automations or restart Home Assistant.

If you intentionally want a pinned blueprint instead of following `main`, import the same GitHub file from a release tag URL.

### 3. Create the automation

1. **Settings → Automations & scenes → Create automation → Use blueprint**.
2. Choose **Codex-LB Rates quota alerts (v2.0.0)**.
3. Under **Sensors and helper**:
   - **Remaining percentage sensors:** add one or more `%` remaining sensors (pool and/or accounts).
   - **Alert state helper:** select the Text helper from step 1 (`input_text.…`).
4. Under **Alert levels**, leave the defaults or tweak thresholds.
5. Under **Notifications**:
   - Leave persistent notification on, or turn it off.
   - Optionally select one or more Companion phones.
   - Optionally edit per-event titles/messages or add custom actions.
6. Save.

Phone notifications require a Home Assistant Companion device that exposes a notify entity. If a selected phone has no notify entity, use **Developer tools → Actions → `notify.send_message`** to confirm that Home Assistant can target that device.

### Behaviour

| Situation | Result |
|-----------|--------|
| Selected sensor's percentage state changes | Checks only that sensor |
| Only an attribute changes while the percentage is unchanged | Does not trigger |
| Home Assistant starts | Checks all selected sensors once |
| Automations reload | Checks all selected sensors once, including quotas already inside an alert band |
| Remaining enters an enabled alert band and its flag is unset | Sends notifications and stores a compact alert token |
| Same band while its flag is set | No duplicate notification |
| Remaining recovers past the rearm rule | Dismisses the matching HA persistent notification and removes the flag |
| Quota reaches the refreshed threshold after a prior low/exceeded alert | Sends refreshed notification, clears low/exceeded state, and stores refreshed state |
| Text helper exists but starts as `unknown` | Initializes it and continues |
| Text helper is missing/unavailable or no sensors are configured | Stops with an explicit error reason in the automation trace |
| Sensor is unknown, non-numeric, outside 0–100, or not `%` | Skips that sensor |

At **0%** with both low and exceeded enabled, only **exceeded** fires; low requires remaining to be above the exceeded threshold. If exceeded is disabled, low can still fire at 0%.

The automation runs in **queued** mode so overlapping sensor state changes are not silently discarded. Key validation, migration, and sensor-evaluation steps also have trace aliases so failures are easier to identify than a generic `Condition: Template condition → Aborted` entry.
