# Agent guide — Codex-LB Rates

Instructions for coding agents working in this repository.

## Releases (Release Please)

This repo uses [Release Please](https://github.com/googleapis/release-please) on pushes to `main`.

| File | Role |
|------|------|
| `.github/workflows/release-please.yml` | Runs Release Please on `main` |
| `release-please-config.json` | Release type + files to bump |
| `.release-please-manifest.json` | Last released version |
| `version.txt` | Simple releaser version source |
| `custom_components/codex_rates/manifest.json` | HACS version (`$.version`, via `extra-files`) |
| `CHANGELOG.md` | Generated / updated by Release Please |

### Normal flow (agents + humans)

1. Open a **feature PR** into `main` with [Conventional Commits](https://www.conventionalcommits.org/) in the **merge commit or squashed commit message** (GitHub squash uses the PR title by default — set it carefully).
2. Merge the feature PR.
3. Release Please opens a **release PR** that bumps versions + `CHANGELOG.md`.
4. Merge the release PR → GitHub creates tag `vX.Y.Z` and the GitHub Release.

Commit prefixes that matter:

| Prefix | SemVer effect |
|--------|----------------|
| `fix:` | patch (`0.3.0` → `0.3.1`) |
| `feat:` | minor (`0.3.0` → `0.4.0`) |
| `feat!:` / `fix!:` / `BREAKING CHANGE:` | major (`0.3.0` → `1.0.0`) |
| `chore:`, `docs:`, `ci:`, `test:` | no release by themselves |

Do **not** hand-edit `manifest.json` / `version.txt` version numbers on feature PRs unless bootstrapping Release Please. Let the release PR own bumps.

### Target a specific version (`Release-As`)

To force the **next** release to a chosen SemVer (e.g. ship the current work as `0.3.1` or jump to `1.0.0`), put this in the **commit body** that lands on `main` (squash commit message or a follow-up commit):

```text
feat: short summary of the change

Optional longer description.

Release-As: 0.3.1
```

Rules for agents:

- Put `Release-As: X.Y.Z` in the **body**, not only the subject line.
- Use it when the user asks to release as a specific version, or when conventional commits would bump the wrong SemVer level.
- After that commit is on `main`, Release Please opens (or updates) a release PR **for exactly that version**.
- Do **not** leave a permanent `"release-as": "..."` in `release-please-config.json` — it would keep re-targeting that version. Prefer the commit footer.
- Empty commit on `main` (maintainers only) also works:

```bash
git commit --allow-empty -m "chore: release 0.3.1" -m "Release-As: 0.3.1"
git push
```

### PR title / squash message checklist

When opening or merging a PR that should release:

1. Confirm desired SemVer with the user if unclear (`patch` vs `minor` vs exact `Release-As`).
2. Set squash title to a conventional commit (`feat: …` / `fix: …`).
3. If targeting an exact version, include `Release-As: X.Y.Z` in the squash commit body.
4. Do not create GitHub releases/tags manually unless the user asks — Release Please does that when the **release PR** merges.
5. If a release PR did not appear after merge: re-run the **Release Please** workflow on `main`, or ask a maintainer to retry the failed run.

### HACS note

HACS reads `custom_components/codex_rates/manifest.json` → `version`. That field is updated by Release Please via `extra-files` in `release-please-config.json`. Keep that jsonpath in sync if the manifest path changes.
