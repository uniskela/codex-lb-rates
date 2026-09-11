# Automations

## Quota alerts blueprint

Notify once per sensor for **low quota**, **quota exceeded**, and **quota refreshed**, then rearm after recovery so you are not spammed. Select one or more remaining-% sensors (pool and/or individual accounts) in a single automation.

| Event | Default | Rearms when |
|-------|---------|-------------|
| Low | remaining ≤ **20%** (and above exceeded) | remaining ≥ 20 + **5** pp |
| Exceeded | remaining ≤ **0%** | remaining > 0 + **1** pp |
| Refreshed | remaining ≥ **100%** after a prior low/exceeded | remaining ≤ **90%** |

Built-in delivery:

- **Home Assistant persistent notification** (UI) — plain text + emoji titles
- **Companion phone(s)** — HTML-bold body, color, icon, subtitle per event
- **Additional actions** — optional TTS/scripts after an alert arms

### Why you need a “helper”

Home Assistant automations do not remember “I already warned about this account” by themselves. Without memory, the blueprint would notify again every time the sensor updates or every 5 minutes while quota stays low.

The **Text helper** is that memory. The blueprint writes short tokens into it, for example:

```text
sensor.codex_lb_pool_all_accounts_5h_remaining::low sensor.alice_5h_remaining::exceeded
```

Meaning: “already alerted low for the pool 5h sensor” and “already alerted exceeded for Alice.” When quota recovers, those tokens are removed so a future drop can alert again.

You do **not** edit this text yourself. Create an empty Text helper, pick it in the blueprint, and leave it alone.

### Migration from the old blueprint

This replaces the single-sensor + Toggle helper blueprint.

1. Delete or disable the old automation.
2. Create a **Text** helper (not Toggle) as below.
3. Re-import/copy the blueprint and create a new automation with your sensors + the Text helper.

### 1. Create the Text helper (click-by-click)

1. In Home Assistant open **Settings → Devices & services**.
2. Open the **Helpers** tab.
3. **Create helper → Text**.
4. Fill in:
   - **Name:** e.g. `Codex quota alerts` (any clear name is fine)
   - **Maximum length:** `255` (important — the default 100 is often too small)
   - **Initial value:** leave **blank**
5. Submit / create.

You should now have an entity like `input_text.codex_quota_alerts`. Its state will stay empty until the first alert fires, then show tokens like the example above.

**Rules of thumb**

- One Text helper **per** quota-alerts automation (do not share across automations).
- Prefer separate automations for **5h** vs **weekly** if you watch many accounts (keeps the 255-character budget comfortable).
- To “reset” alerts manually (force re-notify next time): set the helper’s value back to empty in **Developer tools → States**, or call `input_text.set_value` with an empty string.

### 2. Import the blueprint

Copy from this repository:

`blueprints/automation/codex_rates/quota_warning.yaml`

into your Home Assistant config as:

`config/blueprints/automation/codex_rates/quota_warning.yaml`

Then reload automations, or restart Home Assistant.

You can also open **Settings → Automations & scenes → Blueprints → Import blueprint** and paste the raw GitHub URL for that file on the release tag you installed.

### 3. Create the automation

1. **Settings → Automations & scenes → Create automation → Use blueprint**.
2. Choose **Codex-LB Rates quota alerts**.
3. Under **Sensors and helper**:
   - **Remaining percentage sensors:** add one or more `%` remaining sensors (pool and/or accounts).
   - **Alert state helper:** select the Text helper from step 1 (`input_text.…`).
4. Under **Alert levels**, leave the defaults or tweak thresholds.
5. Under **Notifications** (collapsed):
   - Leave persistent notification on, or turn it off.
   - Optionally pick Companion phones.
   - Optionally edit per-event titles/subtitles/messages.
6. Save.

Phone notifications require the official Home Assistant Companion app. The blueprint calls `notify.mobile_app_<slugified_device_name>` for each selected phone.

If save fails with **Missing input** for the helper, the Text helper was not selected — create it in step 1 and pick it before saving.

### Behaviour

| Situation | Result |
|-----------|--------|
| Remaining enters an enabled alert band and that flag is unset | Sends notifications, stores `entity_id::event` in the Text helper |
| Same band while flag is set | No repeat |
| Remaining recovers past the rearm rule | Clears that notification and removes the flag |
| Quota refreshed | Notifies only after a prior low/exceeded flag for that sensor; clears those flags and notifications |
| Unknown / non-numeric / wrong unit | Sensor skipped; helper unchanged for that sensor |

At **0%** with both low and exceeded enabled, only **exceeded** fires (low requires remaining above the exceeded threshold). If exceeded is disabled, low still fires at 0%.

The Text helper must stay within **255** characters (roughly a handful of sensors × three events). Prefer one automation per window (5h vs weekly) if you monitor many accounts.

Triggers: sensor state changes, Home Assistant start, and every 5 minutes. Mode is **queued** so multi-sensor updates are not dropped.
