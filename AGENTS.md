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

Brand images live in `custom_components/codex_rates/brand/` (`icon.png`, `logo.png`, dark/@2x variants). Home Assistant Core (2026.3+) serves them via `/api/brands/integration/codex_rates/...`. **HACS update/download cards may still show “icon not available”** until HACS uses that local brands proxy — that is a HACS frontend limitation, not a missing file in this repo. Regenerate assets with `python scripts/generate_brand_icon.py` (requires Pillow).

## Blueprint versioning

`blueprints/automation/codex_rates/quota_warning.yaml` has its own SemVer. The blueprint version is **independent** of the integration version managed by Release Please: changing the blueprint does not by itself justify editing `version.txt` or `custom_components/codex_rates/manifest.json`.

Treat the version declared in the blueprint description/name as the canonical blueprint version. When a PR changes blueprint behaviour, inputs, compatibility, notification delivery, migration/state format, or other user-visible semantics:

1. Decide the blueprint SemVer bump: patch for compatible fixes, minor for backward-compatible capabilities, major for breaking/incompatible behaviour or inputs.
2. Update the version in both the blueprint name and `Blueprint version:` description text.
3. Update the current-version/setup wording in `README.md`.
4. Update `docs/automations.md`, including its blueprint version history and any migration/update instructions.
5. Update or add assertions in `tests/test_quota_blueprint.py`. Its version-consistency check must remain green so README/release docs cannot silently drift from the blueprint.
6. Run the full Validate workflow (`pytest`, Hassfest, HACS validation) before treating the PR as ready.

Do not add a non-standard Home Assistant `blueprint.version` key. Home Assistant does not currently define one; the visible name/description plus the repository tests are the version contract used here.

Documentation-only changes that do not alter blueprint behaviour do not need a blueprint SemVer bump, but they must not contradict the canonical version or current behaviour.

## Merging and CODEOWNERS

- [`.github/CODEOWNERS`](.github/CODEOWNERS) assigns **@uniskela** as owner of the whole tree.
- `main` requires a pull request, an approving review, and **code-owner review**.
- Admins can still merge their own PRs (admin enforcement is off so the solo maintainer is not locked out).
- Agents must **not** merge PRs to `main` unless the user explicitly asks and the GitHub actor is allowed; prefer opening PRs for @uniskela to review.
<!-- adhd-hub:project-agent:start -->
<!-- adhd-hub:guidance-version:5 -->
## ADHD Hub continuity

For substantial work in this project:

- If ADHD Hub MCP tools are missing, errored, unauthorized, or otherwise
  unavailable: on the first substantial Hub-worthy turn after detecting the
  outage, the **first line** MUST state that Hub MCP is not available, plus a
  short fix hint (MCP URL → this Hub's `/mcp`, `ADHD_HUB_AUTH_TOKEN`, restart
  the agent; skip/cancel Auth if it hangs until Hub OAuth is enabled). Repeat
  only if Hub status changes, a persistence attempt fails again, or the reply
  could otherwise imply continuity was saved. Then continue the authorized
  work. Never invent Hub state or claim a Hub write succeeded.
- **MCP unavailable** is the Hub continuity trigger (not runtime alone). Use
  the `env-check` skill / `skills/env-check/scripts/check_runtime.sh` for
  CLOUD_AGENT vs LOCAL_WORKSPACE as supporting context (`CURSOR_AGENT`,
  container cues — never `$USER=root` alone). When Hub MCP is unreachable,
  use the forge issue mailbox only when issue-write access is available and
  the authenticated identity is accepted by Hub Inbox authors. Open/update a
  GitHub/Gitea issue titled `[ADHD] …` with a short Goal/Focus/Next/Resume
  cue. Optional labels: `adhd-hub`, `project:<slug>`, `source:cursor`; skip
  labels if the token cannot set them. Recommended: append
  `Made with [ADHD Progress Hub](https://github.com/uniskela/adhd-hub)` under
  a non-imported heading (e.g. `## Attribution`) so it does not land in Resume.
  Prefer short repository-relative summaries; never invent Hub continuity,
  progress, or thread state after a forge-only write.
- CLOUD_AGENT: do not assume machine-installed local skill CLIs (e.g.
  `graphify`) exist. If missing: one-line notice, continue via repo tools /
  committed `graphify-out/` when present; never fabricate graph or Hub state.
  Prefer headless tests and injected env/OIDC over `.env.local`; no native
  browser/macOS-Windows binaries. Hub MCP down still uses the `[ADHD]` forge
  mailbox when allowed. LOCAL_WORKSPACE: those local CLIs may be available;
  local docker / localhost OK; prefer Hub MCP when up.
- Skip Hub for trivial/read-only/tiny work.
- Once per meaningful session: `resolve_project`, then `session_digest` with
  the task query. Reuse resolved context where possible.
- **One thread = one independently finishable outcome** (not the whole repo).
  Before updating a thread, compare new work to that thread's Goal; if it does
  not advance the same outcome, use another thread or create one.
- Known thread → `upsert_progress(thread_id=...)` with compact structured state
  (goal / focus / ≤3 next / blocked if any / resume); omit ritual `content`.
  Do not silently attach to an unrelated open thread.
- `check_overlap` only before potentially new work; reuse only when the Goal
  matches. Different goal → separate thread (`force_new_thread` if needed).
- When leaving mid-task, checkpoint then `pause_thread(thread_id, next_step=...)`
  with one concrete resume action. `mark_done` only the known completed thread
  — never close unrelated overlap results.
- If Hub guidance looks stale (session_digest guidance status, or doctor),
  mention it once, keep using the current MCP contract, and recommend
  `adhd-hub setup . --refresh` — do not nag repeatedly or hand-edit AGENTS.md.
- Summaries only; never secrets, credentials, env files, transcripts, private
  Hub URLs, internal hosts/IPs, or absolute machine paths in public artifacts.
<!-- adhd-hub:project-agent:end -->
