"""Diagnostics support for Codex Rates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_TOTP_SECRET,
    DOMAIN,
)
from .coordinator import CodexRatesCoordinator

TO_REDACT = {
    CONF_PASSWORD,
    CONF_TOTP_SECRET,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_ID_TOKEN,
}

_RESET_FIELDS = (
    "reset_5h",
    "reset_weekly",
    "reset_monthly",
    "reset_spark_5h",
    "reset_spark_weekly",
)
_WINDOW_MINUTE_FIELDS = (
    "window_minutes_5h",
    "window_minutes_weekly",
    "window_minutes_monthly",
    "window_minutes_spark_5h",
    "window_minutes_spark_weekly",
)


def _isoformat(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _remaining_until(
    reset_at: datetime | None, now: datetime
) -> tuple[int | None, float | None]:
    """Return raw seconds and hours until a reset for support diagnostics."""
    if reset_at is None:
        return None, None
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    seconds = round((reset_at.astimezone(timezone.utc) - now).total_seconds())
    return int(seconds), round(seconds / 3600, 3)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: CodexRatesCoordinator = hass.data[DOMAIN][entry.entry_id]
    snapshot = coordinator.data
    now = datetime.now(timezone.utc)
    accounts = []
    if snapshot is not None:
        for account in snapshot.accounts:
            account_data: dict[str, Any] = {
                "account_id": account.account_id,
                "email": account.email,
                "status": account.status,
                "remaining_5h": account.remaining_5h,
                "remaining_weekly": account.remaining_weekly,
                "remaining_monthly": account.remaining_monthly,
                "remaining_spark_5h": account.remaining_spark_5h,
                "remaining_spark_weekly": account.remaining_spark_weekly,
                "reset_credits": account.reset_credits,
                "plan_type": account.plan_type,
                "last_refresh_at": _isoformat(account.last_refresh_at),
            }
            for field in _WINDOW_MINUTE_FIELDS:
                account_data[field] = getattr(account, field)
            for field in _RESET_FIELDS:
                reset_at = getattr(account, field)
                seconds, hours = _remaining_until(reset_at, now)
                account_data[field] = _isoformat(reset_at)
                account_data[f"{field}_remaining_seconds"] = seconds
                account_data[f"{field}_remaining_hours"] = hours
            accounts.append(account_data)
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            TO_REDACT,
        ),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "poll_interval_seconds": coordinator.poll_interval_seconds,
            "last_successful_poll_at": _isoformat(coordinator.last_successful_poll_at),
        },
        "accounts": accounts,
        "pool": None
        if snapshot is None or snapshot.pool is None
        else {
            "remaining_5h_mean": snapshot.pool.remaining_5h.mean,
            "remaining_weekly_mean": snapshot.pool.remaining_weekly.mean,
            "remaining_monthly_mean": snapshot.pool.remaining_monthly.mean,
            "remaining_spark_5h_mean": snapshot.pool.remaining_spark_5h.mean,
            "remaining_spark_weekly_mean": snapshot.pool.remaining_spark_weekly.mean,
            "account_count": snapshot.pool.account_count,
            "active_count": snapshot.pool.active_count,
        },
    }
