# Releases

Codex-LB Rates has two independent version streams: the HACS integration release and the Home Assistant quota-alert blueprint.

## Integration version

The **Integration version** is managed by [Release Please](https://github.com/googleapis/release-please). Release Please bumps versions, updates `CHANGELOG.md`, and publishes GitHub releases.

For agent-oriented instructions (conventional commits, forcing a version with `Release-As`, PR squash checklist), see [AGENTS.md](../AGENTS.md#releases-release-please).

Quick reference:

1. Merge feature work to `main` with `feat:` / `fix:` (or `Release-As: X.Y.Z` in the commit body).
2. Merge the Release Please PR that appears.
3. Tag `vX.Y.Z` and the GitHub Release are created automatically.

Integration version sources bumped together: `version.txt` and `custom_components/codex_rates/manifest.json`.

## Blueprint version

Blueprint version: **2.0.0**

The **Blueprint version** belongs to `blueprints/automation/codex_rates/quota_warning.yaml` and is deliberately independent of the integration version. Release Please does not bump it automatically.

The blueprint SemVer is declared visibly in its name and `Blueprint version:` description. `tests/test_quota_blueprint.py` extracts that value and checks that the current version shown here, in `README.md`, and in `docs/automations.md` stays synchronized.

When blueprint behaviour, inputs, compatibility, state/migration format, or built-in notification delivery changes, update the blueprint SemVer and the associated setup/changelog documentation in the same PR. Follow the maintainer checklist in [AGENTS.md](../AGENTS.md#blueprint-versioning).

Users who imported the blueprint from GitHub update their installed copy with **Settings → Automations & scenes → Blueprints → Re-import blueprint**. A source URL pointing at `main` follows the current blueprint when re-imported; a release-tag URL intentionally remains pinned until the user imports a newer tag.
