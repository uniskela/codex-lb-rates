"""Codex-LB provider — dashboard session + /api/accounts."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import aiohttp
import pyotp

from ..const import LB_LOGIN_GUEST, LB_SESSION_COOKIES
from ..exceptions import CodexRatesApiError, CodexRatesAuthError
from ..models import (
    AccountQuota,
    ProviderSnapshot,
    compute_pool_aggregate,
    parse_iso_datetime,
)

_LOGGER = logging.getLogger(__name__)

# Account rows may carry a provider label; keep ChatGPT/Codex pool members only.
_ACCOUNT_PROVIDERS = frozenset({"openai", "codex", ""})


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
        login_mode: str = "admin",
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/") + "/"
        self._password = password or ""
        self._totp_secret = (totp_secret or "").strip() or None
        self._verify_ssl = verify_ssl
        self._login_mode = (login_mode or "admin").strip().lower()
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
        accounts = [
            self._map_account(item)
            for item in accounts_raw
            if isinstance(item, dict) and _include_account(item)
        ]
        return ProviderSnapshot(accounts=accounts, pool=compute_pool_aggregate(accounts))

    async def _async_login(self) -> None:
        """Establish dashboard session (admin password/TOTP or guest)."""
        session_state = await self._get_session_state()

        authenticated = bool(_first(session_state, "authenticated"))
        totp_required = bool(
            _first(
                session_state,
                "totp_required_on_login",
                "totpRequiredOnLogin",
                "isTotpRequiredOnLogin",
            )
        )

        if authenticated and not totp_required:
            return

        if self._login_mode == LB_LOGIN_GUEST:
            await self._async_guest_login(session_state)
            return

        await self._async_admin_login(session_state, totp_required=totp_required)

    async def _get_session_state(self) -> dict[str, Any]:
        session_url = urljoin(self._base_url, "api/dashboard-auth/session")
        async with self._session.get(
            session_url,
            ssl=self._verify_ssl,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            session_state = await _safe_json(resp)
            self._capture_cookies(resp)
        return session_state if isinstance(session_state, dict) else {}

    async def _async_guest_login(self, session_state: dict[str, Any]) -> None:
        guest_enabled = bool(
            _first(
                session_state,
                "guest_access_enabled",
                "guestAccessEnabled",
            )
        )
        # Older builds may omit the flag; still attempt guest login when selected.
        guest_password_required = bool(
            _first(
                session_state,
                "guest_password_required",
                "guestPasswordRequired",
            )
        )
        if not guest_enabled and (
            "guestAccessEnabled" in session_state or "guest_access_enabled" in session_state
        ):
            raise CodexRatesAuthError("Codex-LB guest access is disabled on this server")
        if guest_password_required and not self._password:
            raise CodexRatesAuthError("Codex-LB guest password is required")

        login_url = urljoin(self._base_url, "api/dashboard-auth/guest/login")
        payload = {"password": self._password} if self._password else {}
        async with self._session.post(
            login_url,
            json=payload,
            ssl=self._verify_ssl,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await _safe_json(resp)
            self._capture_cookies(resp)
            if resp.status >= 400:
                raise CodexRatesAuthError(_lb_error(data, "Codex-LB guest login failed"))

        if data and _first(data, "authenticated") is False:
            raise CodexRatesAuthError("Codex-LB guest login was not authenticated")

        if not self._cookie:
            _LOGGER.debug("Codex-LB guest login completed; relying on session cookie jar")

    async def _async_admin_login(
        self, session_state: dict[str, Any], *, totp_required: bool
    ) -> None:
        password_required = bool(
            _first(
                session_state,
                "password_required",
                "passwordRequired",
                "isPasswordConfigured",
                "password_configured",
                "passwordConfigured",
            )
        )

        if not password_required and not totp_required and not self._password:
            # Dashboard auth disabled — unauthenticated access OK
            self._cookie = None
            return

        if password_required and not self._password:
            raise CodexRatesAuthError("Codex-LB dashboard password is required")

        data: dict[str, Any] | None = None
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
                    raise CodexRatesAuthError(
                        _lb_error(data, "Invalid Codex-LB password")
                    )

            totp_required = bool(
                _first(
                    data or {},
                    "totp_required_on_login",
                    "totpRequiredOnLogin",
                    "isTotpRequiredOnLogin",
                )
                or totp_required
            )

        if totp_required:
            if not self._totp_secret:
                raise CodexRatesAuthError(
                    "Codex-LB requires TOTP — provide a TOTP secret"
                )
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
                    raise CodexRatesAuthError(
                        _lb_error(data, "Invalid Codex-LB TOTP code")
                    )

        if not self._cookie:
            _LOGGER.debug("Codex-LB login completed; relying on session cookie jar")

    def _capture_cookies(self, resp: aiohttp.ClientResponse) -> None:
        """Store dashboard session cookie from response if present."""
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
        # Live Codex-LB JSON is camelCase; docs often show snake_case — accept both.
        usage_raw = _first(item, "usage")
        usage = usage_raw if isinstance(usage_raw, dict) else {}

        primary_remaining = _remaining_from_usage(
            usage,
            item,
            "primary_remaining_percent",
            "primaryRemainingPercent",
            "primary_used_percent",
            "primaryUsedPercent",
        )
        secondary_remaining = _remaining_from_usage(
            usage,
            item,
            "secondary_remaining_percent",
            "secondaryRemainingPercent",
            "secondary_used_percent",
            "secondaryUsedPercent",
        )
        monthly_remaining = _remaining_from_usage(
            usage,
            item,
            "monthly_remaining_percent",
            "monthlyRemainingPercent",
            "monthly_used_percent",
            "monthlyUsedPercent",
        )

        status = str(_first(item, "status") or "unknown").lower()
        account_id = str(_first(item, "account_id", "accountId", "id") or "")
        if not account_id:
            account_id = str(_first(item, "email") or "unknown")

        email = _first(item, "email")
        display_name = _first(item, "display_name", "displayName", "alias")
        plan_type = _first(item, "plan_type", "planType")
        reset_credits = _as_int(
            _first(item, "available_reset_credits", "availableResetCredits")
        )

        return AccountQuota(
            account_id=account_id,
            email=email if isinstance(email, str) else None,
            display_name=display_name if isinstance(display_name, str) else None,
            status=status,
            remaining_5h=primary_remaining,
            remaining_weekly=secondary_remaining,
            remaining_monthly=monthly_remaining,
            used_5h=_used_from_remaining(primary_remaining),
            used_weekly=_used_from_remaining(secondary_remaining),
            used_monthly=_used_from_remaining(monthly_remaining),
            reset_5h=parse_iso_datetime(
                _first(item, "reset_at_primary", "resetAtPrimary")
            ),
            reset_weekly=parse_iso_datetime(
                _first(item, "reset_at_secondary", "resetAtSecondary")
            ),
            reset_monthly=parse_iso_datetime(
                _first(item, "reset_at_monthly", "resetAtMonthly")
            ),
            window_minutes_5h=_as_int(
                _first(item, "window_minutes_primary", "windowMinutesPrimary")
            ),
            window_minutes_weekly=_as_int(
                _first(item, "window_minutes_secondary", "windowMinutesSecondary")
            ),
            window_minutes_monthly=_as_int(
                _first(item, "window_minutes_monthly", "windowMinutesMonthly")
            ),
            plan_type=plan_type if isinstance(plan_type, str) else None,
            credits_balance=_credits_str(item),
            reset_credits=reset_credits,
            reset_credits_expire_at=parse_iso_datetime(
                _first(
                    item,
                    "reset_credit_nearest_expires_at",
                    "resetCreditNearestExpiresAt",
                )
            ),
            last_refresh_at=parse_iso_datetime(
                _first(item, "last_refresh_at", "lastRefreshAt")
            ),
        )


def _include_account(item: dict[str, Any]) -> bool:
    provider = _first(item, "provider")
    if provider is None:
        return True
    return str(provider).strip().lower() in _ACCOUNT_PROVIDERS


def _remaining_from_usage(
    usage: dict[str, Any],
    item: dict[str, Any],
    remaining_snake: str,
    remaining_camel: str,
    used_snake: str,
    used_camel: str,
) -> float | None:
    remaining = _as_float(_first(usage, remaining_snake, remaining_camel))
    if remaining is None:
        remaining = _as_float(_first(item, remaining_snake, remaining_camel))
    if remaining is None:
        used = _as_float(_first(usage, used_snake, used_camel))
        if used is not None:
            remaining = round(100.0 - used, 2)
    return remaining


def _used_from_remaining(remaining: float | None) -> float | None:
    if remaining is None:
        return None
    return round(100.0 - remaining, 2)


def _first(data: dict[str, Any] | None, *keys: str) -> Any:
    """Return the first present key (including explicit nulls)."""
    if not isinstance(data, dict):
        return None
    for key in keys:
        if key in data:
            return data[key]
    return None


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
    for key in (
        "remaining_credits_primary",
        "remainingCreditsPrimary",
        "credits_balance",
        "creditsBalance",
        "balance",
    ):
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
