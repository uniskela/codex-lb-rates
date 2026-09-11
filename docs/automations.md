# Automations

## Quota warning blueprint

Warn once when a Codex-LB Rates **remaining %** sensor drops to or below a threshold, then rearm after remaining recovers by a margin (hysteresis). Uses a dedicated `input_boolean` so the warning state survives restarts.

Built-in delivery channels:

- **Home Assistant persistent notification** (UI bell) — on by default; dismissed when the warning rearms
- **Companion phone(s)** (`mobile_app` devices) — optional; cleared when the warning rearms
- **Additional actions** — optional TTS, scripts, etc.

Phone alerts use a styled title (emoji), subtitle, color, and gauge icon. Edit title/subtitle/message under the Notifications section if you want different wording.

### 1. Create a helper

1. **Settings → Devices & services → Helpers → Create helper → Toggle**.
2. Name it clearly (e.g. `Codex pool 5h warning`).
3. Leave the **initial value unset** so the state persists across restarts.
4. Create **one helper per automation** (pool 5h, pool weekly, and each account window you care about).

### 2. Import the blueprint

Copy from this repository:

`blueprints/automation/codex_rates/quota_warning.yaml`

into your Home Assistant config as:

`config/blueprints/automation/codex_rates/quota_warning.yaml`

Then reload automations, or restart Home Assistant.

You can also open **Settings → Automations & scenes → Blueprints → Import blueprint** and paste the raw GitHub URL for that file on the release tag you installed (for example `v0.1.2`).

### 3. Create the automation

1. **Create automation → Use blueprint → Codex-LB Rates quota warning with hysteresis**.
2. Pick a **remaining %** sensor (unit `%`), for example:
   - Pool: `sensor.…_all_accounts_5h_remaining` / `…_all_accounts_weekly_remaining`
   - Account: `sensor.…_5h_remaining` / `…_weekly_remaining`
3. Select the **Persistent warning helper** from step 1 (required — save fails without it).
4. Set **Warning threshold** (default **20** remaining %).
5. Set **Recovery margin** (default **5** pp). The helper turns off when remaining ≥ threshold + margin.
6. Open **Notifications** (collapsed by default):
   - Leave **Home Assistant persistent notification** enabled, or turn it off.
   - Optionally pick one or more **Phones to notify** (Companion app). Leave empty to skip.
   - Optionally edit title, subtitle, and message.
   - Optionally add **Additional warning actions** (TTS, scripts, etc.).
7. Save.

Phone notifications require the official Home Assistant Companion app with notification permission.

If you see `Missing input warning_state`, the Toggle helper was not selected — create it in step 1 and pick it before saving.

### Behaviour

| Situation | Result |
|-----------|--------|
| Remaining ≤ threshold and helper is **off** | Sends enabled notifications (and any extra actions), then turns the helper **on** |
| Remaining still low and helper is **on** | No repeat warn |
| Remaining ≥ threshold + margin (or strictly above threshold if margin is 0) | Dismisses/clears notifications, turns helper **off** (rearmed) |
| Unknown / non-numeric / wrong unit | Helper left unchanged |

Sensors report **remaining** quota, not consumed usage. Threshold **20** means “20% left” (about 80% used).

Triggers: sensor state changes, Home Assistant start, and every 5 minutes.
