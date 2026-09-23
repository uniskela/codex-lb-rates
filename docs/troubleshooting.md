# Troubleshooting

Start with the symptom that best matches what you see.

## The integration does not appear after installation

1. Confirm this exists:

   `config/custom_components/codex_rates/manifest.json`

2. Restart Home Assistant.
3. Check **Settings → System → Logs** for `codex_rates` or **Codex-LB Rates** errors.
4. If installed through HACS, confirm the integration finished downloading rather than only adding the custom repository.

## Codex-LB: “Could not connect”

Check the **Base URL from Home Assistant's point of view**.

Common causes:

- `127.0.0.1` points at the Home Assistant host/container rather than your Codex-LB machine;
- wrong port;
- Docker/LXC/firewall routing;
- HTTPS certificate verification failure;
- Codex-LB is not listening on an address reachable by Home Assistant.

Try the same URL from another system on the Home Assistant network.

If HTTPS uses a self-signed certificate, prefer fixing trust/certificates. **Verify SSL** can be disabled for the integration connection when necessary, but that removes certificate verification.

## Codex-LB: “Invalid authentication”

Check which login mode the server actually allows:

- **Admin** — dashboard password and optional TOTP secret;
- **Guest** — read-only guest session, with a password only when the server requires one.

Codex-LB API keys do not provide the dashboard-session access this integration needs for account quota data.

If TOTP is enabled, verify the configured secret and system clocks.

## ChatGPT: device-code login is still pending

Finish authorization in the browser, return to Home Assistant, and submit again.

Each Home Assistant submit polls for a limited period instead of blocking the setup flow for the full OAuth code lifetime.

If device-code login is unavailable, use **Browser login + paste callback URL** or another authentication method.

## ChatGPT: the localhost callback page does not load

That can be normal.

For the paste-callback method, the important part is the **URL in the browser address bar**, not whether a local web server successfully renders the page.

Copy the complete URL containing both `code` and `state`, then paste it into Home Assistant.

## auth.json not found

The configured path must be visible **inside Home Assistant**.

For Docker/container installs, a path on the host does not automatically exist in the container. Mount the Codex CLI `auth.json` into the Home Assistant container and use the in-container path.

The default entered by the integration is:

`/config/.codex/auth.json`

## Some quota sensors are missing

This is often expected.

Entities for optional windows are only created when the provider reports a value. Check for:

- monthly quotas — Codex-LB only and only when returned;
- Spark quotas — Codex-LB only and only when returned;
- reset entities — created only when a reset timestamp is returned.

Also remember that rich diagnostic sensors are off by default.

Open **Settings → Devices & services → Codex-LB Rates → Configure** to enable rich sensors.

## “Weekly” changed to “Daily” or another label

Recent integration behaviour uses provider-reported window duration when available.

A secondary window close to:

- 1 day is labelled Daily;
- 7 days is labelled Weekly;
- 30 days is labelled Monthly;
- 1 year is labelled Annual.

This is a display-name correction. Inspect the entity in **Developer tools → States** before changing automations.

## The pool percentage does not match a simple average

That can be correct.

The Codex-LB pool:

- includes every account with a measured value, including `0%`;
- uses capacity weighting when all reporting accounts have usable capacity data;
- falls back to equal weighting for the whole window when capacity data is incomplete;
- keeps accounts with different reported durations and exposes duration-specific values in `by_minutes`.

Inspect the pool sensor's `weighting_method`, `sample_count`, `missing_weight_count`, and `by_minutes` attributes.

## Data looks stale

First compare the value with the source provider.

Then:

1. check Home Assistant logs for provider errors;
2. reload the integration;
3. inspect diagnostics for:
   - `last_update_success`;
   - `poll_interval_seconds`;
   - `last_successful_poll_at`;
4. compare reset timestamps and remaining time in the diagnostics with the provider.

The configured poll interval defaults to 60 seconds and cannot be set below 30 seconds.

A failed poll should not be treated as a successful fresh snapshot.

## Provider HTTP 429 / rate-limit cooldown

When Codex-LB (or the ChatGPT usage endpoint) responds with **HTTP 429**, the
integration treats that as a temporary **poll backoff**, not as account status
`rate_limited`.

What you should see:

1. Entities report an update failure whose reason mentions **HTTP rate limited
   (429)** and a **cooldown until** timestamp.
2. Download diagnostics and check the `coordinator` block for:
   - `rate_limit_active`;
   - `rate_limit_cooldown_until`;
   - `last_rate_limit_at`;
   - `last_rate_limit_retry_after` (from the `Retry-After` header when present).
3. Polling stretches temporarily (using `Retry-After` when valid, otherwise a
   short default backoff, capped) and skips further upstream calls until the
   cooldown ends.
4. After a successful poll, the configured poll interval is restored and
   `rate_limit_active` clears.

Do **not** confuse this with an account's `status` / status sensor value of
`rate_limited`. That value comes from the quota payload (temporary usage
throttle on the account) and is unrelated to this HTTP 429 cooldown UX.

If 429s persist:

- increase the configured poll interval;
- reduce other clients hammering the same Codex-LB dashboard API;
- confirm Codex-LB itself is healthy and not overloaded.

## Reset time looks wrong

Check:

1. Home Assistant's configured timezone;
2. the reset sensor's `resets_at` attribute;
3. the `reset_timezone` attribute;
4. whether the sensor display option is **Countdown** or **Absolute**.

Absolute mode renders the reset in Home Assistant's local timezone. The `resets_at` attribute retains the exact parsed timestamp.

## Quota alert automation aborts

Open the automation **Trace** and look for the named steps.

Common problems:

- the selected Text helper was deleted or is unavailable;
- no remaining-percentage sensors are selected;
- a selected entity is not numeric;
- the selected sensor is not a `%` entity.

A brand-new Text helper in the normal `unknown` state is initialized by blueprint v2 rather than treated as missing.

See [Quota alert automations](automations.md).

## Phone notifications do not arrive

Blueprint v2 targets selected Home Assistant Companion devices through their notify entities using `notify.send_message`.

Check:

1. the Home Assistant Companion integration is connected;
2. the selected phone/device exposes a notify entity;
3. **Developer tools → Actions → `notify.send_message`** can reach that device.

For Companion-specific payloads such as channels, tags, icons, or other advanced fields, use the blueprint's **Additional actions**.

## Download integration diagnostics

In Home Assistant:

1. open **Settings → Devices & services**;
2. open the Codex-LB Rates config entry;
3. open the entry menu;
4. choose **Download diagnostics**.

Diagnostics include useful support data such as:

- provider mode/options;
- last successful poll time;
- configured poll interval;
- HTTP 429 cooldown fields (`rate_limit_active`, `rate_limit_cooldown_until`,
  `last_rate_limit_at`, `last_rate_limit_retry_after`) when a poll backoff is
  active or was recently applied;
- quota values;
- provider-reported window durations;
- exact reset timestamps and calculated time remaining;
- pool counts/aggregates.

Passwords, TOTP secrets, and OAuth tokens are redacted.

> [!CAUTION]
> Diagnostics can still contain account IDs, email addresses, plan information, quota values, and reset timing. Review the file before posting it publicly.

## What to include in a bug report

Useful reports include:

- integration version;
- Home Assistant version;
- provider mode (Codex-LB or ChatGPT / CLI);
- relevant logs/error text;
- expected vs actual behaviour;
- whether a restart/reload changes the result;
- redacted diagnostics when relevant.

Do not post passwords, TOTP secrets, access tokens, refresh tokens, ID tokens, or unreviewed diagnostics.

Use the repository's [issue tracker](https://github.com/uniskela/codex-lb-rates/issues) for bugs. Security-sensitive reports should follow [SECURITY.md](../SECURITY.md).
