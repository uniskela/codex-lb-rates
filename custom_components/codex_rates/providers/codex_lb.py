"""Codex-LB provider — dashboard session + /api/accounts."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import aiohttp
import pyotp

from ..const import LB_SESSION_COOKIES
from ..exceptions import CodexRatesApiError, CodexRatesAuthError
from ..models import (
    AccountQuota,
    ProviderSnapshot,
    compute_pool_aggregate,
    parse_iso_datetime,
)

_LOGGER = logging.getLogger(__name__)


class CodexLbProvider:
    """Fetch per-account quotas from a Codex-LB instance."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        base_url: str,
        password: str | None = None,
        totp_secret: str | None = None,
        verify_ssl: bool = True,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/") + "/"
        self._password = password or ""
        self._totp_secret = (totp_secret or "").strip() or None
        self._verify_ssl = verify_ssl
        self._cookie: str | None = None
        self._cookie_name: str | None = None

    async def async_close(self) -> None:
        """Nothing to close; session owned by caller."""

    async def async_fetch(self) -> ProviderSnapshot:
        """Login if needed and return account snapshot with pool aggregates."""
        try:
            return await self._fetch_accounts()
        except CodexRatesAuthError:
            await self._async_login()
            return await self._fetch_accounts()

    async def async_validate(self) -> ProviderSnapshot:
        """Validate credentials during config flow."""
        await self._async_login()
        return await self._fetch_accounts()

    async def _fetch_accounts(self) -> ProviderSnapshot:
        url = urljoin(self._base_url, "api/accounts")
        headers = self._auth_headers()
        async with self._session.get(
            url,
            headers=headers,
            ssl=self._verify_ssl,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status in (401, 403):
                raise CodexRatesAuthError("Codex-LB authentication required")
            data = await _safe_json(resp)
            if resp.status >= 400:
                raise CodexRatesApiError(f"Codex-LB accounts failed ({resp.status})")
        accounts_raw = data.get("accounts") if isinstance(data, dict) else None
        if not isinstance(accounts_raw, list):
            raise CodexRatesApiError("Codex-LB accounts response missing accounts list")
        accounts = [self._map_account(item) for item in accounts_raw if isinstance(item, dict)]
        return ProviderSnapshot(accounts=accounts, pool=compute_pool_aggregate(accounts))

    async def _async_login(self) -> None:
        """Establish dashboard session when password auth is configured."""
        session_url = urljoin(self._base_url, "api/dashboard-auth/session")
        async with self._session.get(
            session_url,
            ssl=self._verify_ssl,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            session_state = await _safe_json(resp)
            # Capture cookie if already authenticated (auth disabled / existing jar)
            self._capture_cookies(resp)

        if not isinstance(session_state, dict):
            session_state = {}

        authenticated = bool(session_state.get("authenticated"))
        password_required = bool(
            session_state.get("password_required")
            or session_state.get("isPasswordConfigured")
            or session_state.get("password_configured")
        )
        totp_required = bool(
            session_state.get("totp_required_on_login")
            or session_state.get("isTotpRequiredOnLogin")
        )

        if authenticated and not totp_required:
            return

        if not password_required and not totp_required and not self._password:
            # Dashboard auth disabled — unauthenticated access OK
            self._cookie = None
            return

        if password_required and not self._password:
            raise CodexRatesAuthError("Codex-LB dashboard password is required")

        if self._password:
            login_url = urljoin(self._base_url, "api/dashboard-auth/password/login")
            async with self._session.post(
                login_url,
                json={"password": self._password},
                ssl=self._verify_ssl,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await _safe_json(resp)
                self._capture_cookies(resp)
                if resp.status >= 400:
                    raise CodexRatesAuthError(_lb_error(data, "Invalid Codex-LB password"))

            totp_required = bool(
                (data or {}).get("totp_required_on_login")
                or (data or {}).get("isTotpRequiredOnLogin")
                or totp_required
            )

        if totp_required:
            if not self._totp_secret:
                raise CodexRatesAuthError("Codex-LB requires TOTP — provide a TOTP secret")
            code = pyotp.TOTP(self._totp_secret).now()
            totp_url = urljoin(self._base_url, "api/dashboard-auth/totp/verify")
            async with self._session.post(
                totp_url,
                json={"code": code, "totp_code": code},
                ssl=self._verify_ssl,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await _safe_json(resp)
                self._capture_cookies(resp)
                if resp.status >= 400:
                    raise CodexRatesAuthError(_lb_error(data, "Invalid Codex-LB TOTP code"))

        if not self._cookie:
            # Cookie jar on shared session may hold it; also try Set-Cookie parse failure
            _LOGGER.debug("Codex-LB login completed; relying on session cookie jar")

    def _capture_cookies(self, resp: aiohttp.ClientResponse) -> None:
        """Store dashboard session cookie from response if present."""
        # Prefer cookie jar (handles multiple Set-Cookie)
        for name in LB_SESSION_COOKIES:
            if name in resp.cookies:
                morsel = resp.cookies.get(name)
                if morsel is not None and morsel.value:
                    self._cookie_name = name
                    self._cookie = morsel.value
                    return
        raw = resp.headers.getall("Set-Cookie", [])
        for header in raw:
            for name in LB_SESSION_COOKIES:
                prefix = f"{name}="
                if prefix in header:
                    part = header.split(prefix, 1)[1].split(";", 1)[0]
                    if part:
                        self._cookie_name = name
                        self._cookie = part
                        return

    def _auth_headers(self) -> dict[str, str]:
        if self._cookie and self._cookie_name:
            return {"Cookie": f"{self._cookie_name}={self._cookie}"}
        return {}

    @staticmethod
    def _map_account(item: dict[str, Any]) -> AccountQuota:
        usage = item.get("usage") if isinstance(item.get("usage"), dict) else {}
        primary_remaining = _as_float(
            usage.get("primary_remaining_percent", item.get("primary_remaining_percent"))
        )
        secondary_remaining = _as_float(
            usage.get("secondary_remaining_percent", item.get("secondary_remaining_percent"))
        )
        # Some deployments expose used_percent instead
        if primary_remaining is None and usage.get("primary_used_percent") is not None:
            used = _as_float(usage.get("primary_used_percent"))
            primary_remaining = None if used is None else round(100.0 - used, 2)
        if secondary_remaining is None and usage.get("secondary_used_percent") is not None:
            used = _as_float(usage.get("secondary_used_percent"))
            secondary_remaining = None if used is None else round(100.0 - used, 2)

        status = str(item.get("status") or "unknown").lower()
        account_id = str(item.get("account_id") or item.get("id") or "")
        if not account_id:
            account_id = str(item.get("email") or "unknown")

        return AccountQuota(
            account_id=account_id,
            email=item.get("email") if isinstance(item.get("email"), str) else None,
            display_name=item.get("display_name")
            if isinstance(item.get("display_name"), str)
            else None,
            status=status,
            remaining_5h=primary_remaining,
            remaining_weekly=secondary_remaining,
            used_5h=None if primary_remaining is None else round(100.0 - primary_remaining, 2),
            used_weekly=None
            if secondary_remaining is None
            else round(100.0 - secondary_remaining, 2),
            reset_5h=parse_iso_datetime(item.get("reset_at_primary")),
            reset_weekly=parse_iso_datetime(item.get("reset_at_secondary")),
            window_minutes_5h=_as_int(item.get("window_minutes_primary")),
            window_minutes_weekly=_as_int(item.get("window_minutes_secondary")),
            plan_type=item.get("plan_type") if isinstance(item.get("plan_type"), str) else None,
            credits_balance=_credits_str(item),
            last_refresh_at=parse_iso_datetime(item.get("last_refresh_at")),
        )


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


def _credits_str(item: dict[str, Any]) -> str | None:
    for key in ("remaining_credits_primary", "credits_balance", "balance"):
        if key in item and item[key] is not None:
            return str(item[key])
    return None


def _lb_error(data: dict[str, Any] | None, fallback: str) -> str:
    if not isinstance(data, dict):
        return fallback
    err = data.get("error")
    if isinstance(err, dict) and isinstance(err.get("message"), str):
        return err["message"]
    if isinstance(data.get("message"), str):
        return data["message"]
    return fallback


async def _safe_json(resp: aiohttp.ClientResponse) -> dict[str, Any]:
    try:
        data = await resp.json(content_type=None)
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}
