# Codex Rates Home Assistant Integration — Design

**Date:** 2026-09-10  
**Status:** Approved

## Goal

HACS-installable Home Assistant custom integration (`codex_rates`) that exposes Codex **5-hour** and **weekly** quota remaining (plus status/reset times) for Lovelace dashboards.

## Modes

1. **Codex-LB** — dashboard password (± optional TOTP); poll `GET /api/accounts`; one config entry fans out all pooled accounts; pool-level aggregate sensors.
2. **ChatGPT / Codex CLI** — OAuth (device code or PKCE + paste callback), `auth.json` import, or advanced token paste; one account per config entry; auto token refresh.

## Auth

- Secrets live in config-entry storage only (never YAML).
- Never log passwords, TOTP secrets, tokens, or session cookies.
- Codex-LB: no API keys (management API is dashboard-session only). Optional empty password when dashboard auth is disabled.
- ChatGPT: do not bind port 1455; use device code or pasted `http://localhost:1455/auth/callback?...` URL. OAuth client matches Codex CLI / Codex-LB.

## Entities

**Per account (dashboard-ready):** 5h remaining %, weekly remaining %, 5h reset, weekly reset, status.

**Rich (options toggle):** plan type, credits balance, last refresh.

**Codex-LB pool device:** mean remaining % for 5h and weekly across **active** accounts (null windows skipped); attributes `min`, `max`, `account_count`, `active_count`.

## Runtime

- `DataUpdateCoordinator`, default poll 60s (min 30).
- Auth failures → `ConfigEntryAuthFailed` after re-login/refresh attempt.
- Partial windows → sensor `unknown`, not hard failure.

## Out of scope (v1)

Pause/reactivate accounts, Core submission, MQTT sidecar.
