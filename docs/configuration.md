# Configuration

Codex-LB Rates supports two provider modes. The setup screen validates the connection before the config entry is created.

## Codex-LB mode

Choose **Codex-LB** when Home Assistant should read quota data from a Codex-LB server.

### Connection fields

| Field | What to enter |
|---|---|
| **Name** | Optional display name for the Home Assistant config entry |
| **Base URL** | The URL Home Assistant can use to reach Codex-LB, for example `http://192.168.1.10:2455` |
| **Login mode** | **Admin** or **Guest** |
| **Password** | Admin dashboard password, or guest password when your server requires one |
| **TOTP secret** | Optional; admin mode only |
| **Verify SSL** | Keep enabled for a normally trusted HTTPS certificate |

The default URL shown by the integration is `http://127.0.0.1:2455`. That only works when Codex-LB is actually reachable from Home Assistant at that address.

### Admin vs Guest

**Admin** uses the Codex-LB dashboard login. Use it when guest access is unavailable or when your server requires the administrative session to read account data.

**Guest** uses Codex-LB's read-only guest session when the server has guest access enabled.

Leave the password blank when the selected login mode does not require one.

> [!IMPORTANT]
> Codex-LB API keys are not a replacement for the dashboard/guest session here. The account quota endpoint used by the integration requires dashboard-session authentication.

### HTTPS and self-signed certificates

Keep **Verify SSL** enabled whenever possible.

If you use a self-signed certificate that Home Assistant does not trust, the connection can fail validation. Disabling verification can make that connection work, but it removes certificate verification for this integration connection. Prefer installing a trusted certificate or making your internal CA trusted where practical.

## ChatGPT / Codex CLI mode

Use this mode when you are not using Codex-LB and want quota sensors for a single ChatGPT account.

The integration offers four authentication methods.

| Method | Recommended for | Notes |
|---|---|---|
| **Device code** | Most users, especially remote/Docker Home Assistant | Recommended first choice |
| **Browser login + paste callback URL** | Interactive login when device code is unavailable | Paste the complete `localhost:1455` callback URL after sign-in |
| **Import Codex CLI auth.json** | Existing Codex CLI authentication mounted into Home Assistant | The file path must exist **inside Home Assistant** |
| **Paste tokens** | Advanced recovery/testing | Requires an access token and ChatGPT account ID; refresh/ID tokens are optional |

### Device-code login

1. Choose **Device code**.
2. Open the verification URL displayed by Home Assistant.
3. Enter the displayed code and authorize the account.
4. Return to Home Assistant and submit the form.

Home Assistant waits for authorization for a limited period on each submit. If the screen says authorization is still pending, finish the login and submit again.

### Browser login + paste callback

1. Choose **Browser login + paste callback URL**.
2. Open the authorization link shown by Home Assistant.
3. Sign in.
4. The browser redirects to a localhost URL similar to:

   `http://localhost:1455/auth/callback?code=...&state=...`

5. The page itself does not need to load successfully.
6. Copy the **entire URL from the browser address bar** and paste it into Home Assistant.

The integration validates the OAuth state before exchanging the code.

### Import auth.json

The default path is:

`/config/.codex/auth.json`

That path is inside Home Assistant, not necessarily the path on the Docker host or another machine.

For a containerised Home Assistant installation, bind-mount or otherwise make the Codex CLI `auth.json` visible inside the Home Assistant container, then enter the in-container path.

The integration reads the account/tokens during setup and also retains the auth.json path for that authentication method.

### Paste tokens

This is intended for advanced use. The setup requires:

- access token;
- ChatGPT account ID.

Refresh token and ID token are optional. If a refresh token is available, the provider can renew the access token when supported.

## Multiple ChatGPT accounts

Run **Add integration → Codex-LB Rates** again for each ChatGPT account.

Each ChatGPT account ID is unique within Home Assistant, so the same account cannot be added twice.

## Integration options

Open:

**Settings → Devices & services → Codex-LB Rates → Configure**

Available options:

| Option | Default | Range / behaviour |
|---|---:|---|
| **Poll interval** | 60 seconds | 30–3600 seconds |
| **Enable rich sensors** | Off | Adds plan, credits balance, last-refresh, and request-count diagnostic sensors when data exists |
| **Reset sensor display** | Countdown | `countdown` shows values such as `2d 04h`; `absolute` shows a local `YYYY-MM-DD HH:MM` value |

Changing the reset display only changes the human-readable sensor state. Reset sensors keep the exact provider timestamp in the `resets_at` attribute.

## What happens after configuration

The integration polls the provider and reconciles Home Assistant entities against each successful response.

That means optional quota windows can appear or disappear when the upstream provider starts or stops reporting them. User-disabled or hidden entity preferences are preserved for temporarily missing quota windows where possible.

Continue with [Entities and data](entities.md).
