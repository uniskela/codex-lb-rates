# Installation

The recommended installation method is **HACS**. A manual install is also supported.

## Requirements

- A reasonably current Home Assistant installation.
- Network access from Home Assistant to:
  - your Codex-LB server when using **Codex-LB mode**, or
  - ChatGPT/OpenAI authentication and usage endpoints when using **ChatGPT / Codex CLI mode**.
- Home Assistant must be able to restart after the custom integration is installed or updated.

## Install with HACS

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=uniskela&repository=codex-lb-rates&category=integration)

If the button does not work for your setup:

1. Open **HACS**.
2. Open the integrations section.
3. Add this repository as a custom repository:
   - Repository: `https://github.com/uniskela/codex-lb-rates`
   - Type: **Integration**
4. Install **Codex-LB Rates**.
5. Restart Home Assistant.

## Manual installation

1. Download or clone this repository.
2. Copy:

   `custom_components/codex_rates`

   into your Home Assistant configuration directory as:

   `config/custom_components/codex_rates`

3. Restart Home Assistant.

Your final layout should include a file such as:

`config/custom_components/codex_rates/manifest.json`

## Add the integration

After Home Assistant restarts:

1. Open **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **Codex-LB Rates**.
4. Choose:
   - **Codex-LB**, or
   - **ChatGPT / Codex CLI**.
5. Complete the provider-specific setup in [Configuration](configuration.md).

## Confirm it is working

After setup, open **Settings → Devices & services → Codex-LB Rates**.

You should see:

- one device per monitored account; and
- in Codex-LB mode, a **Codex-LB pool** device when the server reports quota data.

The exact sensors depend on what the provider returns. See [Entities and data](entities.md).

## Installing the quota-alert blueprint

The notification blueprint is optional and is versioned separately from the integration.

Do not copy it as part of the integration installation unless you want quota notifications. Follow [Quota alert automations](automations.md) for the one-click import and required Text helper.

## Updating later

HACS updates the Python integration, while the quota-alert blueprint is updated by **re-importing the blueprint** in Home Assistant. These are separate update paths.

See [Upgrading](upgrading.md) before updating.
