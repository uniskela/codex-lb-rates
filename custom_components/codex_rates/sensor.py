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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ACCOUNT_COUNT,
    ATTR_ACCOUNT_ID,
    ATTR_ACTIVE_COUNT,
    ATTR_EMAIL,
    ATTR_MAX,
    ATTR_MIN,
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
from .models import AccountQuota, ProviderSnapshot, WindowAggregate


@dataclass(frozen=True, kw_only=True)
class CodexRatesSensorDescription(SensorEntityDescription):
    """Sensor description with value / attribute extractors."""

    value_fn: Callable[[AccountQuota], float | str | datetime | None]
    attrs_fn: Callable[[AccountQuota], dict[str, Any]] | None = None
    rich: bool = False


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
        key="reset_5h",
        translation_key="reset_5h",
        name="5h resets",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda a: a.reset_5h,
    ),
    CodexRatesSensorDescription(
        key="reset_weekly",
        translation_key="reset_weekly",
        name="Weekly resets",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda a: a.reset_weekly,
    ),
    CodexRatesSensorDescription(
        key="status",
        translation_key="status",
        name="Status",
        value_fn=lambda a: a.status,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: CodexRatesCoordinator = hass.data[DOMAIN][entry.entry_id]
    rich = entry.options.get(CONF_RICH_SENSORS, DEFAULT_RICH_SENSORS)

    entities: list[SensorEntity] = []
    snapshot = coordinator.data
    if snapshot is None:
        await coordinator.async_config_entry_first_refresh()
        snapshot = coordinator.data

    assert snapshot is not None

    for account in snapshot.accounts:
        for description in ACCOUNT_SENSORS:
            if description.rich and not rich:
                continue
            entities.append(
                CodexAccountSensor(coordinator, entry, account.account_id, description)
            )

    if entry.data.get(CONF_MODE) == MODE_CODEX_LB:
        entities.append(CodexPoolSensor(coordinator, entry, "remaining_5h", "All accounts 5h remaining"))
        entities.append(
            CodexPoolSensor(coordinator, entry, "remaining_weekly", "All accounts weekly remaining")
        )

    async_add_entities(entities)

    @callback
    def _check_new_accounts() -> None:
        if coordinator.data is None:
            return
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
                if description.rich and not rich:
                    continue
                new_entities.append(
                    CodexAccountSensor(coordinator, entry, account.account_id, description)
                )
        if new_entities:
            entities.extend(new_entities)
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_check_new_accounts))


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
        account = _account_from_data(coordinator.data, account_id)
        name = account.name if account else account_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{account_id}")},
            name=name,
            manufacturer="Codex Rates",
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
            manufacturer="Codex Rates",
            model="Codex-LB",
        )

    def _window(self) -> WindowAggregate | None:
        data = self.coordinator.data
        if data is None or data.pool is None:
            return None
        if self._key == "remaining_5h":
            return data.pool.remaining_5h
        return data.pool.remaining_weekly

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
        return {
            ATTR_MIN: window.min,
            ATTR_MAX: window.max,
            ATTR_ACCOUNT_COUNT: data.pool.account_count,
            ATTR_ACTIVE_COUNT: data.pool.active_count,
        }
