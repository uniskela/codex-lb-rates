# Upgrading

Codex-LB Rates has **two independent update paths**:

1. the Home Assistant custom integration; and
2. the optional quota-alert blueprint.

Updating one does not automatically update the other.

## Update the integration with HACS

1. Open **HACS**.
2. Open **Codex-LB Rates**.
3. Install the available update.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Codex-LB Rates** and confirm the integration loads normally.

A restart matters because this is a Python custom integration. After restart, hard-refresh any dashboard that uses `custom:codex-rates-card` if the browser still shows a cached card bundle.

Check the repository [CHANGELOG](../CHANGELOG.md) or GitHub release before updating when you want to review behaviour changes first.

## Update a manual installation

1. Download the desired release.
2. Replace the contents of:

   `config/custom_components/codex_rates/`

   with the files from the same directory in that release.
3. Do not mix files from different releases.
4. Restart Home Assistant.

## Update the quota-alert blueprint

The blueprint has its **own version number**, independent of the integration release.

If you originally imported it from GitHub:

1. Open **Settings → Automations & scenes → Blueprints**.
2. Find **Codex-LB Rates quota alerts**.
3. Open its menu.
4. Choose **Re-import blueprint**.
5. Reload automations if Home Assistant asks.

An import URL pointing at `main` follows the current blueprint when you re-import. A URL pinned to a Git tag intentionally stays on that release.

See [Quota alert automations](automations.md) for the current blueprint version and migration notes.

## What normally survives an integration update

The integration uses stable unique IDs tied to the Home Assistant config entry, account ID, and sensor key. Normal upgrades are designed to preserve registry entities and user customisation.

Provider-dependent optional windows can still appear or disappear when the upstream data changes.

The integration also cleans up stale account devices from older or no-longer-reported account identifiers after successful provider responses.

## If an update appears to remove a quota sensor

Before rolling back:

1. Check whether the provider still reports that window.
2. Reload the integration once.
3. Check **Developer tools → States** for the entity.
4. Review the integration diagnostics.
5. Check the release notes for a change to window reconciliation or naming.

Monthly and Spark sensors are deliberately conditional; their absence can be valid.

## Rollback

For HACS, select an older repository release if HACS offers it, restart Home Assistant, and then confirm your config entry still loads.

For manual installs, restore the complete `custom_components/codex_rates` directory from one known-good release and restart.

Do not copy only selected Python files between versions.

## Before reporting an upgrade regression

Collect:

- previous version;
- new version;
- provider mode;
- whether the issue remains after a Home Assistant restart;
- relevant logs;
- integration diagnostics after reviewing them for account information.

See [Troubleshooting](troubleshooting.md).
