"""The Codex Rates integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_POLL_INTERVAL, DOMAIN
from .coordinator import CodexRatesCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
_OPTIONS_SNAPSHOT = "options_snapshot"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Codex Rates from a config entry."""
    coordinator = CodexRatesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.data[DOMAIN][f"{entry.entry_id}_{_OPTIONS_SNAPSHOT}"] = dict(entry.options)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: CodexRatesCoordinator | None = hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_{_OPTIONS_SNAPSHOT}", None)
        if coordinator is not None:
            await coordinator.async_shutdown_provider()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry updates.

    Token refresh updates ``entry.data`` and must only rebuild the provider.
    Options changes (poll interval / rich sensors) reload platforms.
    """
    coordinator: CodexRatesCoordinator = hass.data[DOMAIN][entry.entry_id]
    interval = entry.options.get(CONF_POLL_INTERVAL, 60)
    coordinator.update_interval = timedelta(seconds=max(30, int(interval)))
    coordinator.rebuild_provider()

    key = f"{entry.entry_id}_{_OPTIONS_SNAPSHOT}"
    previous = hass.data[DOMAIN].get(key)
    current = dict(entry.options)
    if previous != current:
        hass.data[DOMAIN][key] = current
        await hass.config_entries.async_reload(entry.entry_id)
