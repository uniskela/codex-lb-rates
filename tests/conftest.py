"""Pytest configuration for Codex Rates."""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _ensure_homeassistant_stubs() -> None:
    """Minimal stubs so unit tests can import the integration package."""
    if "homeassistant" in sys.modules:
        return

    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    def _mod(name: str) -> types.ModuleType:
        module = types.ModuleType(name)
        sys.modules[name] = module
        return module

    config_entries = _mod("homeassistant.config_entries")

    class ConfigEntry:  # noqa: D401
        """Stub."""

    class ConfigFlow:
        """Stub."""

        def __init_subclass__(cls, **kwargs):  # noqa: ANN003
            return None

    class OptionsFlow:
        """Stub."""

    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow

    const = _mod("homeassistant.const")
    const.Platform = types.SimpleNamespace(SENSOR="sensor")
    const.CONF_NAME = "name"
    const.PERCENTAGE = "%"
    const.EntityCategory = types.SimpleNamespace(DIAGNOSTIC="diagnostic")

    core = _mod("homeassistant.core")
    core.HomeAssistant = object
    core.callback = lambda f: f

    exceptions = _mod("homeassistant.exceptions")

    class ConfigEntryAuthFailed(Exception):
        """Stub."""

    exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed

    data_entry_flow = _mod("homeassistant.data_entry_flow")
    data_entry_flow.FlowResult = dict

    util = _mod("homeassistant.util")
    dt_util = _mod("homeassistant.util.dt")
    from datetime import timezone

    dt_util.DEFAULT_TIME_ZONE = timezone.utc
    dt_util.as_local = lambda dt: dt.astimezone(dt_util.DEFAULT_TIME_ZONE)
    util.dt = dt_util

    helpers = _mod("homeassistant.helpers")
    aiohttp_client = _mod("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass, **kwargs: None
    aiohttp_client.async_create_clientsession = lambda hass, **kwargs: None
    selector = _mod("homeassistant.helpers.selector")

    class _TextSelectorConfig:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.__dict__.update(kwargs)

    class _TextSelectorType:
        PASSWORD = "password"

    class _TextSelector:
        def __init__(self, config=None):  # noqa: ANN001
            self.config = config

    selector.TextSelector = _TextSelector
    selector.TextSelectorConfig = _TextSelectorConfig
    selector.TextSelectorType = _TextSelectorType

    update_coordinator = _mod("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            pass

        def __class_getitem__(cls, item):  # noqa: ANN001
            return cls

    class UpdateFailed(Exception):
        """Stub."""

    class CoordinatorEntity:
        def __init__(self, coordinator):  # noqa: ANN001
            self.coordinator = coordinator

        def __class_getitem__(cls, item):  # noqa: ANN001
            return cls

        @property
        def available(self) -> bool:
            return True

    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed
    update_coordinator.CoordinatorEntity = CoordinatorEntity

    device_registry = _mod("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = dict
    device_registry.async_get = lambda hass: None
    device_registry.async_entries_for_config_entry = lambda registry, entry_id: []

    entity_registry = _mod("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda hass: None
    entity_registry.async_entries_for_config_entry = lambda registry, entry_id: []

    entity_platform = _mod("homeassistant.helpers.entity_platform")
    entity_platform.AddEntitiesCallback = object

    diagnostics = _mod("homeassistant.components.diagnostics")
    diagnostics.async_redact_data = lambda data, to_redact: data

    _mod("homeassistant.components")
    sensor = _mod("homeassistant.components.sensor")

    from dataclasses import dataclass

    @dataclass(frozen=True)
    class SensorEntityDescription:
        key: str | None = None
        name: str | object | None = None
        translation_key: str | None = None
        native_unit_of_measurement: str | None = None
        device_class: object | None = None
        state_class: object | None = None
        entity_category: object | None = None
        entity_registry_enabled_default: bool = True
        entity_registry_visible_default: bool = True
        force_update: bool = False
        options: list[str] | None = None
        icon: str | None = None
        has_entity_name: bool = False
        unit_of_measurement: str | None = None

    class SensorEntity:
        """Small entity lifecycle contract used by platform reconciliation tests."""

        hass = None

        @property
        def unique_id(self):
            return self._attr_unique_id

        async def async_remove(self, *, force_remove=False):
            self.hass.entities.pop(self.unique_id, None)
            self.hass.removed.append(self.unique_id)
            if force_remove:
                force_removed = getattr(self.hass, "force_removed", None)
                if force_removed is not None:
                    force_removed.append(self.unique_id)
            else:
                soft_removed = getattr(self.hass, "soft_removed", None)
                if soft_removed is not None:
                    soft_removed.append(self.unique_id)

    sensor.SensorEntity = SensorEntity
    sensor.SensorEntityDescription = SensorEntityDescription
    sensor.SensorDeviceClass = types.SimpleNamespace(TIMESTAMP="timestamp", ENUM="enum")
    sensor.SensorStateClass = types.SimpleNamespace(MEASUREMENT="measurement")


_ensure_homeassistant_stubs()
