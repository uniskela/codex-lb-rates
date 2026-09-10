"""Sensor platform for Codex Rates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ACCOUNT_COUNT,
    ATTR_ACCOUNT_ID,
    ATTR_ACTIVE_COUNT,
    ATTR_BY_MINUTES,
    ATTR_EMAIL,
    ATTR_MAX,
    ATTR_MIN,
    ATTR_RESET_CREDITS_EXPIRE,
    ATTR_RESETS_AT,
    ATTR_USED_PERCENT,
    ATTR_WINDOW_MINUTES,
    CONF_MODE,
    CONF_RICH_SENSORS,
    DEFAULT_RICH_SENSORS,
    DOMAIN,
    MODE_CODEX_LB,
    POOL_DEVICE_ID,
)
from .coordinator import CodexRatesCoordinator
from .models import AccountQuota, ProviderSnapshot, WindowAggregate, format_reset_countdown


@dataclass(frozen=True, kw_only=True)
class CodexRatesSensorDescription(SensorEntityDescription):
    """Sensor description with value / attribute extractors."""

    value_fn: Callable[[AccountQuota], float | str | datetime | None]
    attrs_fn: Callable[[AccountQuota], dict[str, Any]] | None = None
    rich: bool = False
    codex_lb_only: bool = False


def _reset_attrs(when: datetime | None, account: AccountQuota) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        ATTR_ACCOUNT_ID: account.account_id,
        ATTR_EMAIL: account.email,
    }
    if when is not None:
        attrs[ATTR_RESETS_AT] = when.isoformat()
    return attrs


ACCOUNT_SENSORS: tuple[CodexRatesSensorDescription, ...] = (
    CodexRatesSensorDescription(
        key="remaining_5h",
        translation_key="remaining_5h",
        name="5h remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.remaining_5h,
        attrs_fn=lambda a: _pct_attrs(a.used_5h, a.window_minutes_5h, a),
    ),
    CodexRatesSensorDescription(
        key="remaining_weekly",
        translation_key="remaining_weekly",
        name="Weekly remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.remaining_weekly,
        attrs_fn=lambda a: _pct_attrs(a.used_weekly, a.window_minutes_weekly, a),
    ),
    CodexRatesSensorDescription(
        key="remaining_monthly",
        translation_key="remaining_monthly",
        name="Monthly remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.remaining_monthly,
        attrs_fn=lambda a: _pct_attrs(a.used_monthly, a.window_minutes_monthly, a),
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="reset_5h",
        translation_key="reset_5h",
        name="5h resets",
        value_fn=lambda a: format_reset_countdown(a.reset_5h),
        attrs_fn=lambda a: _reset_attrs(a.reset_5h, a),
    ),
    CodexRatesSensorDescription(
        key="reset_weekly",
        translation_key="reset_weekly",
        name="Weekly resets",
        value_fn=lambda a: format_reset_countdown(a.reset_weekly),
        attrs_fn=lambda a: _reset_attrs(a.reset_weekly, a),
    ),
    CodexRatesSensorDescription(
        key="reset_monthly",
        translation_key="reset_monthly",
        name="Monthly resets",
        value_fn=lambda a: format_reset_countdown(a.reset_monthly),
        attrs_fn=lambda a: _reset_attrs(a.reset_monthly, a),
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="status",
        translation_key="status",
        name="Status",
        value_fn=lambda a: a.status,
    ),
    CodexRatesSensorDescription(
        key="reset_credits",
        translation_key="reset_credits",
        name="Reset credits",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.reset_credits,
        attrs_fn=lambda a: {
            ATTR_ACCOUNT_ID: a.account_id,
            ATTR_EMAIL: a.email,
            **(
                {ATTR_RESET_CREDITS_EXPIRE: a.reset_credits_expire_at.isoformat()}
                if a.reset_credits_expire_at is not None
                else {}
            ),
        },
    ),
    CodexRatesSensorDescription(
        key="plan_type",
        translation_key="plan_type",
        name="Plan",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.plan_type,
        rich=True,
    ),
    CodexRatesSensorDescription(
        key="credits_balance",
        translation_key="credits_balance",
        name="Credits balance",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.credits_balance,
        rich=True,
    ),
    CodexRatesSensorDescription(
        key="last_refresh",
        translation_key="last_refresh",
        name="Last refresh",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.last_refresh_at,
        rich=True,
    ),
)

_POOL_SENSOR_KEYS = frozenset(
    {"remaining_5h", "remaining_weekly", "remaining_monthly"}
)
_ACCOUNT_SENSOR_KEYS = frozenset(desc.key for desc in ACCOUNT_SENSORS)


def _include_description(
    description: CodexRatesSensorDescription, *, rich: bool, is_codex_lb: bool
) -> bool:
    if description.rich and not rich:
        return False
    if description.codex_lb_only and not is_codex_lb:
        return False
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: CodexRatesCoordinator = hass.data[DOMAIN][entry.entry_id]
    rich = entry.options.get(CONF_RICH_SENSORS, DEFAULT_RICH_SENSORS)
    is_codex_lb = entry.data.get(CONF_MODE) == MODE_CODEX_LB

    entities: list[SensorEntity] = []
    snapshot = coordinator.data
    if snapshot is None:
        await coordinator.async_config_entry_first_refresh()
        snapshot = coordinator.data

    assert snapshot is not None

    for account in snapshot.accounts:
        for description in ACCOUNT_SENSORS:
            if not _include_description(description, rich=rich, is_codex_lb=is_codex_lb):
                continue
            entities.append(
                CodexAccountSensor(coordinator, entry, account.account_id, description)
            )

    if is_codex_lb:
        entities.append(CodexPoolSensor(coordinator, entry, "remaining_5h", "All accounts 5h remaining"))
        entities.append(
            CodexPoolSensor(coordinator, entry, "remaining_weekly", "All accounts weekly remaining")
        )
        entities.append(
            CodexPoolSensor(
                coordinator, entry, "remaining_monthly", "All accounts monthly remaining"
            )
        )

    async_add_entities(entities)
    cleanup_orphan_devices(hass, entry, snapshot)

    @callback
    def _on_coordinator_update() -> None:
        if coordinator.data is None:
            return
        cleanup_orphan_devices(hass, entry, coordinator.data)
        existing = {
            (e.account_id if isinstance(e, CodexAccountSensor) else None)
            for e in entities
            if isinstance(e, CodexAccountSensor)
        }
        new_entities: list[SensorEntity] = []
        for account in coordinator.data.accounts:
            if account.account_id in existing:
                continue
            for description in ACCOUNT_SENSORS:
                if not _include_description(
                    description, rich=rich, is_codex_lb=is_codex_lb
                ):
                    continue
                new_entities.append(
                    CodexAccountSensor(coordinator, entry, account.account_id, description)
                )
        if new_entities:
            entities.extend(new_entities)
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))


def live_device_suffixes(entry: ConfigEntry, snapshot: ProviderSnapshot) -> set[str]:
    """Return device identifier suffixes that should remain for this entry."""
    live = {account.account_id for account in snapshot.accounts}
    if entry.data.get(CONF_MODE) == MODE_CODEX_LB:
        live.add(POOL_DEVICE_ID)
    return live


def allowed_sensor_keys(entry: ConfigEntry) -> set[str]:
    """Sensor keys that should exist for this config entry's mode/options."""
    rich = entry.options.get(CONF_RICH_SENSORS, DEFAULT_RICH_SENSORS)
    is_codex_lb = entry.data.get(CONF_MODE) == MODE_CODEX_LB
    keys = {
        description.key
        for description in ACCOUNT_SENSORS
        if _include_description(description, rich=rich, is_codex_lb=is_codex_lb)
    }
    if is_codex_lb:
        keys |= set(_POOL_SENSOR_KEYS)
    return keys


def account_id_from_unique_id(entry_id: str, unique_id: str) -> str | None:
    """Extract account/pool id from a sensor unique_id."""
    prefix = f"{entry_id}_"
    if not unique_id.startswith(prefix):
        return None
    rest = unique_id[len(prefix) :]
    for key in _ACCOUNT_SENSOR_KEYS | _POOL_SENSOR_KEYS:
        suffix = f"_{key}"
        if rest.endswith(suffix):
            return rest[: -len(suffix)]
    return None


def sensor_key_from_unique_id(entry_id: str, unique_id: str) -> str | None:
    """Extract sensor key from a sensor unique_id."""
    prefix = f"{entry_id}_"
    if not unique_id.startswith(prefix):
        return None
    rest = unique_id[len(prefix) :]
    for key in _ACCOUNT_SENSOR_KEYS | _POOL_SENSOR_KEYS:
        suffix = f"_{key}"
        if rest.endswith(suffix):
            return key
    return None


def cleanup_orphan_devices(
    hass: HomeAssistant, entry: ConfigEntry, snapshot: ProviderSnapshot
) -> list[str]:
    """Remove devices/entities that no longer belong to this entry.

    Drops:
    - devices for account_ids missing from the snapshot
    - entities for those accounts
    - entities whose sensor key is not created for the current mode/options
      (e.g. ChatGPT monthly remaining/resets left from an older version)

    Returns removed device identifier suffixes (for tests).
    """
    live = live_device_suffixes(entry, snapshot)
    allowed_keys = allowed_sensor_keys(entry)
    prefix = f"{entry.entry_id}_"
    removed: list[str] = []

    try:
        device_reg = dr.async_get(hass)
    except Exception:  # noqa: BLE001 — stubs / early init
        device_reg = None

    if device_reg is not None:
        for device in list(device_reg.devices.values()):
            for domain, ident in device.identifiers:
                if domain != DOMAIN or not ident.startswith(prefix):
                    continue
                suffix = ident[len(prefix) :]
                if suffix not in live:
                    device_reg.async_remove_device(device.id)
                    removed.append(suffix)

    try:
        entity_reg = er.async_get(hass)
    except Exception:  # noqa: BLE001
        entity_reg = None

    if entity_reg is not None:
        for entity in list(er.async_entries_for_config_entry(entity_reg, entry.entry_id)):
            unique_id = entity.unique_id or ""
            account_id = account_id_from_unique_id(entry.entry_id, unique_id)
            sensor_key = sensor_key_from_unique_id(entry.entry_id, unique_id)
            if account_id is None or sensor_key is None:
                continue
            if account_id not in live or sensor_key not in allowed_keys:
                entity_reg.async_remove(entity.entity_id)

    return removed


def _pct_attrs(
    used: float | None, window_minutes: int | None, account: AccountQuota
) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        ATTR_ACCOUNT_ID: account.account_id,
        ATTR_EMAIL: account.email,
    }
    if used is not None:
        attrs[ATTR_USED_PERCENT] = used
    if window_minutes is not None:
        attrs[ATTR_WINDOW_MINUTES] = window_minutes
    return attrs


def _account_from_data(data: ProviderSnapshot | None, account_id: str) -> AccountQuota | None:
    if data is None:
        return None
    for account in data.accounts:
        if account.account_id == account_id:
            return account
    return None


class CodexAccountSensor(CoordinatorEntity[CodexRatesCoordinator], SensorEntity):
    """Sensor bound to a single account quota field."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CodexRatesCoordinator,
        entry: ConfigEntry,
        account_id: str,
        description: CodexRatesSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.account_id = account_id
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{account_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        account = _account_from_data(self.coordinator.data, self.account_id)
        name = account.name if account else self.account_id
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self.account_id}")},
            name=name,
            manufacturer="Codex-LB Rates",
            model="ChatGPT / Codex account",
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and _account_from_data(self.coordinator.data, self.account_id) is not None
        )

    @property
    def native_value(self) -> float | str | datetime | None:
        account = _account_from_data(self.coordinator.data, self.account_id)
        if account is None:
            return None
        return self.entity_description.value_fn(account)  # type: ignore[attr-defined]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        account = _account_from_data(self.coordinator.data, self.account_id)
        if account is None:
            return None
        attrs_fn = self.entity_description.attrs_fn  # type: ignore[attr-defined]
        if attrs_fn is None:
            return {ATTR_ACCOUNT_ID: account.account_id, ATTR_EMAIL: account.email}
        return attrs_fn(account)


class CodexPoolSensor(CoordinatorEntity[CodexRatesCoordinator], SensorEntity):
    """Pool aggregate remaining % for Codex-LB."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: CodexRatesCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{POOL_DEVICE_ID}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{POOL_DEVICE_ID}")},
            name="Codex-LB pool",
            manufacturer="Codex-LB Rates",
            model="Codex-LB",
        )

    def _window(self) -> WindowAggregate | None:
        data = self.coordinator.data
        if data is None or data.pool is None:
            return None
        if self._key == "remaining_5h":
            return data.pool.remaining_5h
        if self._key == "remaining_weekly":
            return data.pool.remaining_weekly
        return data.pool.remaining_monthly

    @property
    def native_value(self) -> float | None:
        window = self._window()
        return None if window is None else window.mean

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        window = self._window()
        if data is None or data.pool is None or window is None:
            return None
        attrs: dict[str, Any] = {
            ATTR_MIN: window.min,
            ATTR_MAX: window.max,
            ATTR_ACCOUNT_COUNT: data.pool.account_count,
            ATTR_ACTIVE_COUNT: data.pool.active_count,
        }
        if window.window_minutes is not None:
            attrs[ATTR_WINDOW_MINUTES] = window.window_minutes
        if window.by_minutes:
            attrs[ATTR_BY_MINUTES] = {
                str(minutes): mean for minutes, mean in window.by_minutes.items()
            }
        return attrs
