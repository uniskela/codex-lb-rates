# Quota alert automations

Blueprint version: **2.0.0**

The **Codex-LB Rates quota alerts** blueprint watches one or more remaining-percentage sensors and can notify when quota becomes **low**, is **exceeded**, or is **refreshed**.

It remembers which alerts have already fired so a sensor sitting at the same low level does not repeatedly notify you.

## Quick setup

You need:

- at least one Codex-LB Rates remaining-% sensor;
- one Home Assistant **Text helper** dedicated to this automation;
- optional Home Assistant Companion phone devices.

### 1. Create the Text helper

1. Open **Settings → Devices & services → Helpers**.
2. Select **Create helper → Text**.
3. Name it something like `Codex quota alerts`.
4. Set the maximum length to **255**.
5. Leave its initial value blank.
6. Create the helper.

Use **one Text helper per copy of the blueprint**. Do not share the same helper between multiple quota-alert automations.

### 2. Import the blueprint

[![Open your Home Assistant instance and import the Codex-LB Rates quota alert blueprint.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Funiskela%2Fcodex-lb-rates%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fcodex_rates%2Fquota_warning.yaml)

Or manually copy:

`blueprints/automation/codex_rates/quota_warning.yaml`

to:

`config/blueprints/automation/codex_rates/quota_warning.yaml`

Then reload automations or restart Home Assistant.

### 3. Create the automation

1. Open **Settings → Automations & scenes → Create automation → Use blueprint**.
2. Select **Codex-LB Rates quota alerts (v2.0.0)**.
3. Choose one or more **remaining percentage sensors**.
4. Select the Text helper from step 1.
5. Keep the default thresholds or change them.
6. Choose whether to create Home Assistant persistent notifications.
7. Optionally select Companion phones.
8. Save.

## Default alert levels

| Event | Default condition | Rearms when |
|---|---|---|
| **Low** | remaining ≤ 20%, while above the exceeded band | remaining recovers by 5 percentage points |
| **Exceeded** | remaining ≤ 0% | remaining rises more than 1 percentage point above the exceeded threshold |
| **Refreshed** | remaining ≥ 100% after a prior low/exceeded alert | remaining later drops to ≤ 90% |

These are based on **remaining percentage**. A low threshold of 20 means “20% or less remains”, not “20% has been used”.

At 0%, with both low and exceeded alerts enabled, **Exceeded** takes priority. If exceeded alerts are disabled, the low alert can still trigger at 0%.

## How triggering works

Blueprint v2 is event-driven.

During normal operation, the blueprint reacts when a selected sensor's **percentage state changes**. It checks all configured sensors when Home Assistant starts and again when automations reload.

Attribute-only changes do not trigger a normal quota evaluation.

This is **not a threshold-only trigger**. The state change starts the automation, then the action logic evaluates the exact thresholds, hysteresis, and rearm conditions. Keeping those comparisons in one place preserves the intended ≤ / ≥ behaviour.

## Why the Text helper is required

Home Assistant automations do not otherwise remember that a warning has already been sent.

The helper stores compact tokens such as:

```text
3a19c7de:l 7e0814aa:e
```

You do not need to understand or edit these values.

The suffix means:

- `l` — low;
- `e` — exceeded;
- `r` — refreshed.

The first part is a compact stable hash of the entity ID. This keeps multi-sensor state small enough for Home Assistant's 255-character Text helper.

A brand-new helper that temporarily reports `unknown` is initialized automatically.

To deliberately reset all alert memory for this automation, set its Text helper value to blank.

## Notification delivery

The blueprint can send:

- Home Assistant persistent notifications;
- notifications to selected Companion phone devices;
- your own **Additional actions** after an alert is armed.

Blueprint v2 targets selected Companion devices through Home Assistant notify entities with `notify.send_message`. It does not guess a `notify.mobile_app_*` action from the phone's display name.

The standard built-in phone notification sends a title and message.

For Companion-specific payloads such as custom channels, tags, colours, icons, or other advanced options, use **Additional actions**.

## Additional actions

Use **Additional actions after any alert** for things such as:

- TTS;
- a script;
- a light/LED warning;
- a Discord/webhook automation;
- a Companion-specific notification action.

The blueprint exposes useful variables to those actions, including the selected remaining entity, current percentage, friendly name, event type, and notification subtitle.

## Hysteresis and alert spam

Hysteresis means an alert has to recover far enough before the same alert can fire again.

Example with the defaults:

1. quota falls to 20% → Low fires once;
2. quota moves between 18% and 22% → no repeat Low alert;
3. quota recovers to the configured rearm point;
4. a later drop can trigger Low again.

This avoids repeated notifications from small percentage changes around a threshold.

## Updating the blueprint

The blueprint version is independent of the integration version.

If you imported it from GitHub:

1. open **Settings → Automations & scenes → Blueprints**;
2. open the menu for Codex-LB Rates quota alerts;
3. choose **Re-import blueprint**;
4. reload automations if prompted.

The one-click import above points to `main`, so re-importing follows the current blueprint.

If you intentionally imported a URL pinned to a release tag, it remains pinned until you choose a newer source.

See [Upgrading](upgrading.md) for the difference between integration and blueprint updates.

## Upgrading from blueprint v1

Existing v1 multi-sensor automations can keep their selected sensors, thresholds, Text helper, and phone selections.

On its first run, v2 recognizes the older full-entity alert tokens and rewrites them to the compact token format automatically.

Version 2 also changed phone delivery to direct notify-entity device targeting and removed timer-based quota checks in favour of percentage state changes plus startup/reload catch-up.

## Behaviour reference

| Situation | Result |
|---|---|
| A selected percentage state changes | Checks that sensor |
| Only an attribute changes | Does not trigger normal evaluation |
| Home Assistant starts | Checks all selected sensors |
| Automations reload | Checks all selected sensors |
| A sensor enters an enabled band and is not already armed | Sends configured notifications and remembers the event |
| A sensor stays in the same armed band | Does not send a duplicate |
| A sensor recovers past the rearm rule | Clears the corresponding alert state |
| Quota reaches the refreshed threshold after low/exceeded | Sends refreshed and clears previous low/exceeded state |
| Text helper is newly created and reports `unknown` | Initializes the helper and continues |
| Text helper is missing/unavailable | Stops with an explicit trace error |
| Sensor is non-numeric, outside 0–100, or not a `%` entity | Skips that sensor |

The automation uses queued mode so overlapping state changes are not silently discarded.

## Troubleshooting

If the automation stops unexpectedly:

1. open the automation **Trace**;
2. check the named steps, especially **Validate alert-state helper**;
3. confirm the Text helper still exists;
4. confirm at least one remaining-% sensor is selected;
5. inspect the sensor in **Developer tools → States** and confirm it is numeric with unit `%`.

For phone problems, test **Developer tools → Actions → `notify.send_message`** against the selected Companion device.

More help: [Troubleshooting](troubleshooting.md).
