# Releases

Codex-LB Rates uses [Release Please](https://github.com/googleapis/release-please) to bump versions, update `CHANGELOG.md`, and publish GitHub releases.

For agent-oriented instructions (conventional commits, forcing a version with `Release-As`, PR squash checklist), see [AGENTS.md](../AGENTS.md#releases-release-please).

## Quick reference

1. Merge feature work to `main` with `feat:` / `fix:` (or `Release-As: X.Y.Z` in the commit body).
2. Merge the Release Please PR that appears.
3. Tag `vX.Y.Z` and the GitHub Release are created automatically.

Version sources bumped together: `version.txt` and `custom_components/codex_rates/manifest.json`.
