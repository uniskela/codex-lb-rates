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

### Migration from the old blueprint

This replaces the single-sensor + Toggle helper blueprint.

1. Delete or disable the old automation.
2. Create a **Text** helper (not Toggle) with **Maximum length 255** and empty initial value.
3. Re-import/copy the blueprint and create a new automation with your sensors + the Text helper.

### 1. Create a Text helper

1. **Settings → Devices & services → Helpers → Create helper → Text**.
2. Name it clearly (e.g. `Codex quota alerts`).
3. Set **Maximum length** to **255**.
4. Leave the **initial value empty** so state persists across restarts.
5. One helper per automation.

### 2. Import the blueprint

Copy from this repository:

`blueprints/automation/codex_rates/quota_warning.yaml`

into your Home Assistant config as:

`config/blueprints/automation/codex_rates/quota_warning.yaml`

Then reload automations, or restart Home Assistant.

You can also open **Settings → Automations & scenes → Blueprints → Import blueprint** and paste the raw GitHub URL for that file on the release tag you installed.

### 3. Create the automation

1. **Create automation → Use blueprint → Codex-LB Rates quota alerts**.
2. Select one or more **remaining %** sensors, for example:
   - Pool: `sensor.…_all_accounts_5h_remaining` / `…_all_accounts_weekly_remaining`
   - Accounts: `sensor.…_5h_remaining` / `…_weekly_remaining`
3. Select the **Alert state** Text helper from step 1 (required).
4. Under **Alert levels**, enable the events you want and adjust thresholds if needed.
5. Open **Notifications**:
   - Leave persistent notification enabled, or turn it off.
   - Optionally pick Companion phones.
   - Optionally edit per-event titles/subtitles/messages.
6. Save.

Phone notifications require the official Home Assistant Companion app. The blueprint calls `notify.mobile_app_<slugified_device_name>` for each selected phone.

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
