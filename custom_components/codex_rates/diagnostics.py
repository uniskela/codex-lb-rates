"""Diagnostics support for Codex Rates."""

from __future__ import annotations

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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: CodexRatesCoordinator = hass.data[DOMAIN][entry.entry_id]
    snapshot = coordinator.data
    accounts = []
    if snapshot is not None:
        for account in snapshot.accounts:
            accounts.append(
                {
                    "account_id": account.account_id,
                    "email": account.email,
                    "status": account.status,
                    "remaining_5h": account.remaining_5h,
                    "remaining_weekly": account.remaining_weekly,
                    "remaining_monthly": account.remaining_monthly,
                    "reset_credits": account.reset_credits,
                    "plan_type": account.plan_type,
                }
            )
    return {
        "entry": async_redact_data(
            {"title": entry.title, "data": dict(entry.data), "options": dict(entry.options)},
            TO_REDACT,
        ),
        "accounts": accounts,
        "pool": None
        if snapshot is None or snapshot.pool is None
        else {
            "remaining_5h_mean": snapshot.pool.remaining_5h.mean,
            "remaining_weekly_mean": snapshot.pool.remaining_weekly.mean,
            "remaining_monthly_mean": snapshot.pool.remaining_monthly.mean,
            "account_count": snapshot.pool.account_count,
            "active_count": snapshot.pool.active_count,
        },
    }
