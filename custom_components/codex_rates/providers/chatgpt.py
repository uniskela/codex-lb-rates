"""ChatGPT / Codex CLI usage provider."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Awaitable

import aiohttp

from ..const import CHATGPT_USAGE_URL
from ..exceptions import CodexRatesApiError, CodexRatesAuthError
from ..models import AccountQuota, ProviderSnapshot, parse_iso_datetime, remaining_from_used
from ..oauth import (
    OAuthTokens,
    account_id_from_id_token,
    email_from_id_token,
    refresh_access_token,
)

_LOGGER = logging.getLogger(__name__)

TokenSaver = Callable[[dict[str, str]], Awaitable[None]]


class ChatGptProvider:
    """Fetch quota for a single ChatGPT / Codex account."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        access_token: str,
        account_id: str,
        refresh_token: str | None = None,
        id_token: str | None = None,
        email: str | None = None,
        auth_json_path: str | None = None,
        usage_url: str = CHATGPT_USAGE_URL,
        on_tokens_updated: TokenSaver | None = None,
    ) -> None:
        self._session = session
        self._access_token = access_token
        self._account_id = account_id
        self._refresh_token = refresh_token or ""
        self._id_token = id_token or ""
        self._email = email
        self._auth_json_path = auth_json_path
        self._usage_url = usage_url
        self._on_tokens_updated = on_tokens_updated

    async def async_close(self) -> None:
        """Nothing owned."""

    async def async_fetch(self) -> ProviderSnapshot:
        """Return single-account snapshot."""
        if self._auth_json_path:
            self._load_auth_json_if_present()
        try:
            account = await self._fetch_usage()
        except CodexRatesAuthError:
            await self._async_refresh()
            account = await self._fetch_usage()
        return ProviderSnapshot(accounts=[account], pool=None)

    async def async_validate(self) -> ProviderSnapshot:
        """Validate tokens during config flow."""
        return await self.async_fetch()

    def _load_auth_json_if_present(self) -> None:
        path = Path(self._auth_json_path or "")
        if not path.is_file():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            _LOGGER.warning("Failed to read auth.json: %s", err)
            return
        tokens = raw.get("tokens") if isinstance(raw.get("tokens"), dict) else raw
        if not isinstance(tokens, dict):
            return
        access = tokens.get("access_token") or tokens.get("accessToken")
        refresh = tokens.get("refresh_token") or tokens.get("refreshToken")
        id_token = tokens.get("id_token") or tokens.get("idToken")
        account_id = tokens.get("account_id") or tokens.get("accountId")
        if isinstance(access, str) and access:
            self._access_token = access
        if isinstance(refresh, str) and refresh:
            self._refresh_token = refresh
        if isinstance(id_token, str) and id_token:
            self._id_token = id_token
            self._email = self._email or email_from_id_token(id_token)
            if not account_id:
                account_id = account_id_from_id_token(id_token)
        if isinstance(account_id, str) and account_id:
            self._account_id = account_id

    async def _async_refresh(self) -> None:
        if not self._refresh_token:
            raise CodexRatesAuthError("ChatGPT access token expired and no refresh_token available")
        tokens = await refresh_access_token(self._session, refresh_token=self._refresh_token)
        self._access_token = tokens.access_token
        self._refresh_token = tokens.refresh_token
        if tokens.id_token:
            self._id_token = tokens.id_token
            self._email = self._email or email_from_id_token(tokens.id_token)
            maybe_id = account_id_from_id_token(tokens.id_token)
            if maybe_id:
                self._account_id = maybe_id
        if self._on_tokens_updated:
            await self._on_tokens_updated(
                {
                    "access_token": self._access_token,
                    "refresh_token": self._refresh_token,
                    "id_token": self._id_token,
                    "account_id": self._account_id,
                }
            )

    async def _fetch_usage(self) -> AccountQuota:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "ChatGPT-Account-Id": self._account_id,
            "chatgpt-account-id": self._account_id,
        }
        async with self._session.get(
            self._usage_url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            data = await _safe_json(resp)
            if resp.status in (401, 403):
                raise CodexRatesAuthError("ChatGPT usage authentication failed")
            if resp.status >= 400:
                raise CodexRatesApiError(f"ChatGPT usage failed ({resp.status})")
        return self._map_usage(data)

    def _map_usage(self, data: dict[str, Any]) -> AccountQuota:
        rate = data.get("rate_limit") or data.get("rateLimits") or {}
        if not isinstance(rate, dict):
            rate = {}
        primary = rate.get("primary_window") or rate.get("primary") or {}
        secondary = rate.get("secondary_window") or rate.get("secondary") or {}
        if not isinstance(primary, dict):
            primary = {}
        if not isinstance(secondary, dict):
            secondary = {}

        used_5h = _as_float(primary.get("used_percent") or primary.get("usedPercent"))
        used_weekly = _as_float(secondary.get("used_percent") or secondary.get("usedPercent"))
        remaining_5h = remaining_from_used(used_5h)
        remaining_weekly = remaining_from_used(used_weekly)

        reset_5h = parse_iso_datetime(
            primary.get("reset_at") or primary.get("resetsAt") or primary.get("resetAt")
        )
        reset_weekly = parse_iso_datetime(
            secondary.get("reset_at") or secondary.get("resetsAt") or secondary.get("resetAt")
        )

        window_5h = _as_int(
            primary.get("limit_window_seconds")
            or primary.get("windowDurationMins")
            or primary.get("window_minutes")
        )
        # Normalize minutes if seconds provided
        if window_5h and window_5h > 1000:
            window_5h = window_5h // 60
        window_weekly = _as_int(
            secondary.get("limit_window_seconds")
            or secondary.get("windowDurationMins")
            or secondary.get("window_minutes")
        )
        if window_weekly and window_weekly > 1000:
            window_weekly = window_weekly // 60

        allowed = rate.get("allowed")
        limit_reached = rate.get("limit_reached") or rate.get("rateLimitReachedType")
        status = "active"
        if limit_reached or allowed is False:
            # Prefer weekly exhaustion when secondary is 100%
            if used_weekly is not None and used_weekly >= 100:
                status = "quota_exceeded"
            else:
                status = "rate_limited"

        credits = data.get("credits") if isinstance(data.get("credits"), dict) else {}
        balance = credits.get("balance") if isinstance(credits, dict) else None
        plan = data.get("plan_type") or rate.get("planType") or rate.get("plan_type")

        return AccountQuota(
            account_id=self._account_id,
            email=self._email,
            display_name=self._email,
            status=status,
            remaining_5h=remaining_5h,
            remaining_weekly=remaining_weekly,
            used_5h=used_5h,
            used_weekly=used_weekly,
            reset_5h=reset_5h,
            reset_weekly=reset_weekly,
            window_minutes_5h=window_5h,
            window_minutes_weekly=window_weekly,
            plan_type=plan if isinstance(plan, str) else None,
            credits_balance=str(balance) if balance is not None else None,
        )


def load_auth_json(path: str) -> dict[str, str]:
    """Load Codex CLI auth.json into a flat token dict."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    tokens = raw.get("tokens") if isinstance(raw.get("tokens"), dict) else raw
    if not isinstance(tokens, dict):
        raise CodexRatesAuthError("Invalid auth.json structure")
    access = tokens.get("access_token") or tokens.get("accessToken")
    refresh = tokens.get("refresh_token") or tokens.get("refreshToken")
    id_token = tokens.get("id_token") or tokens.get("idToken")
    account_id = tokens.get("account_id") or tokens.get("accountId")
    if not isinstance(access, str) or not access:
        raise CodexRatesAuthError("auth.json missing access_token")
    if not isinstance(account_id, str) or not account_id:
        if isinstance(id_token, str):
            account_id = account_id_from_id_token(id_token)
        if not account_id:
            raise CodexRatesAuthError("auth.json missing account_id")
    result = {
        "access_token": access,
        "account_id": account_id,
    }
    if isinstance(refresh, str) and refresh:
        result["refresh_token"] = refresh
    if isinstance(id_token, str) and id_token:
        result["id_token"] = id_token
        email = email_from_id_token(id_token)
        if email:
            result["email"] = email
    return result


def tokens_from_oauth(tokens: OAuthTokens) -> dict[str, str]:
    """Flatten OAuthTokens for config entry storage."""
    account_id = account_id_from_id_token(tokens.id_token) or "unknown"
    result = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "id_token": tokens.id_token,
        "account_id": account_id,
    }
    email = email_from_id_token(tokens.id_token)
    if email:
        result["email"] = email
    return result


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _safe_json(resp: aiohttp.ClientResponse) -> dict[str, Any]:
    try:
        data = await resp.json(content_type=None)
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}
