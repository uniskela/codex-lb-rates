"""Sensor platform for Codex Rates."""

from __future__ import annotations

import asyncio
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
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACCOUNT_COUNT,
    ATTR_ACCOUNT_ID,
    ATTR_ACTIVE_COUNT,
    ATTR_ADDITIONAL_QUOTAS,
    ATTR_BY_MINUTES,
    ATTR_CACHED_INPUT_TOKENS,
    ATTR_EMAIL,
    ATTR_MAX,
    ATTR_MIN,
    ATTR_REMAINING_PERCENT,
    ATTR_RESET_CREDITS_EXPIRE,
    ATTR_RESETS_AT,
    ATTR_TOTAL_COST_USD,
    ATTR_TOTAL_TOKENS,
    ATTR_USED_PERCENT,
    ATTR_WINDOW_MINUTES,
    CONF_MODE,
    CONF_RESET_DISPLAY,
    CONF_RICH_SENSORS,
    CONF_USED_PERCENT_SENSORS,
    DEFAULT_RESET_DISPLAY,
    DEFAULT_RICH_SENSORS,
    DEFAULT_USED_PERCENT_SENSORS,
    DOMAIN,
    MODE_CODEX_LB,
    POOL_DEVICE_ID,
    RESET_DISPLAY_ABSOLUTE,
)
from .coordinator import CodexRatesCoordinator
from .models import (
    AccountQuota,
    ProviderSnapshot,
    WindowAggregate,
    format_reset_countdown,
)

STATUS_ICONS = {
    "active": "mdi:check-circle-outline",
    "rate_limited": "mdi:timer-sand",
    "quota_exceeded": "mdi:alert-circle-outline",
    "paused": "mdi:pause-circle-outline",
    "reauth_required": "mdi:account-key-outline",
    "deactivated": "mdi:account-off-outline",
    "unknown": "mdi:help-circle-outline",
}


@dataclass(frozen=True, kw_only=True)
class CodexRatesSensorDescription(SensorEntityDescription):
    """Sensor description with value / attribute extractors."""

    value_fn: Callable[[AccountQuota], float | str | datetime | None]
    attrs_fn: Callable[[AccountQuota], dict[str, Any]] | None = None
    rich: bool = False
    used_percent: bool = False
    codex_lb_only: bool = False


def _reset_attrs(when: datetime | None, account: AccountQuota) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        ATTR_ACCOUNT_ID: account.account_id,
        ATTR_EMAIL: account.email,
    }
    if when is not None:
        attrs[ATTR_RESETS_AT] = when.isoformat()
        attrs["reset_timezone"] = str(dt_util.as_local(when).tzinfo)
    return attrs


def _status_attrs(account: AccountQuota) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        ATTR_ACCOUNT_ID: account.account_id,
        ATTR_EMAIL: account.email,
        "raw_status": account.status,
    }
    if account.additional_quotas:
        attrs[ATTR_ADDITIONAL_QUOTAS] = [
            quota.as_dict() for quota in account.additional_quotas
        ]
    return attrs


def _request_usage_attrs(account: AccountQuota) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        ATTR_ACCOUNT_ID: account.account_id,
        ATTR_EMAIL: account.email,
    }
    if account.total_tokens is not None:
        attrs[ATTR_TOTAL_TOKENS] = account.total_tokens
    if account.cached_input_tokens is not None:
        attrs[ATTR_CACHED_INPUT_TOKENS] = account.cached_input_tokens
    if account.total_cost_usd is not None:
        attrs[ATTR_TOTAL_COST_USD] = account.total_cost_usd
    return attrs


def _absolute_reset(when: datetime | None) -> str | None:
    """Render a fixed local date/time; HA timestamp rows are relative by default."""
    return (
        dt_util.as_local(when).strftime("%Y-%m-%d %H:%M") if when is not None else None
    )


def _format_reset_display(when: datetime | None, entry: ConfigEntry) -> str | None:
    """Render reset state from the configured display mode."""
    mode = entry.options.get(CONF_RESET_DISPLAY, DEFAULT_RESET_DISPLAY)
    if mode == RESET_DISPLAY_ABSOLUTE:
        return _absolute_reset(when)
    return format_reset_countdown(when)


def _is_reset_window_key(key: str) -> bool:
    return key.startswith("reset_") and key != "reset_credits"


_WINDOW_LABELS: tuple[tuple[int, str], ...] = (
    (5 * 60, "5h"),
    (24 * 60, "Daily"),
    (7 * 24 * 60, "Weekly"),
    (30 * 24 * 60, "Monthly"),
    (365 * 24 * 60, "Annual"),
)
_WINDOW_MINUTES_ATTRS = {
    "remaining_5h": "window_minutes_5h",
    "used_5h": "window_minutes_5h",
    "reset_5h": "window_minutes_5h",
    "remaining_weekly": "window_minutes_weekly",
    "used_weekly": "window_minutes_weekly",
    "reset_weekly": "window_minutes_weekly",
    "remaining_monthly": "window_minutes_monthly",
    "used_monthly": "window_minutes_monthly",
    "reset_monthly": "window_minutes_monthly",
    "remaining_spark_5h": "window_minutes_spark_5h",
    "used_spark_5h": "window_minutes_spark_5h",
    "reset_spark_5h": "window_minutes_spark_5h",
    "remaining_spark_weekly": "window_minutes_spark_weekly",
    "used_spark_weekly": "window_minutes_spark_weekly",
    "reset_spark_weekly": "window_minutes_spark_weekly",
}


def _window_duration_label(window_minutes: int | None) -> str | None:
    """Return the same common duration labels used by the Codex client."""
    if window_minutes is None or window_minutes <= 0:
        return None
    for expected, label in _WINDOW_LABELS:
        if expected * 0.95 <= window_minutes <= expected * 1.05:
            return label
    return None


def _fallback_window_label(key: str) -> str:
    if "monthly" in key:
        return "Monthly"
    if "weekly" in key:
        return "Secondary"
    return "Primary"


def _account_window_name(account: AccountQuota, key: str) -> str | None:
    """Build an account sensor name from the provider-reported window duration."""
    attr = _WINDOW_MINUTES_ATTRS.get(key)
    if attr is None:
        return None
    label = _window_duration_label(getattr(account, attr))
    if label is None:
        return None
    prefix = "Spark " if "spark" in key else ""
    if key.startswith("reset_"):
        suffix = "resets"
    elif key.startswith("used_"):
        suffix = "used"
    else:
        suffix = "remaining"
    return f"{prefix}{label} {suffix}"


def _pool_window_metric(key: str) -> str:
    """Return the pool sensor metric word for this key (remaining or used)."""
    return "used" if key.startswith("used_") else "remaining"


def _pool_aggregate_key(key: str) -> str:
    """Map a pool sensor key onto the PoolAggregate remaining_* field name."""
    if key.startswith("used_"):
        return f"remaining_{key[len('used_'):]}"
    return key


def _pool_window_name(
    key: str, window: WindowAggregate, fallback_name: str
) -> str:
    """Build a pool name from a uniform duration, or generic name for mixed windows."""
    label = _window_duration_label(window.window_minutes)
    if label is None:
        if not window.by_minutes:
            return fallback_name
        label = _fallback_window_label(key)
    if label != "5h":
        label = label.lower()
    prefix = "Spark " if "spark" in key else ""
    return f"All accounts {prefix}{label} {_pool_window_metric(key)}"


ACCOUNT_SENSORS: tuple[CodexRatesSensorDescription, ...] = (
    CodexRatesSensorDescription(
        key="remaining_5h",
        icon="mdi:timer-sand",
        translation_key="remaining_5h",
        name="5h remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.remaining_5h,
        attrs_fn=lambda a: _pct_attrs(a.used_5h, a.window_minutes_5h, a),
    ),
    CodexRatesSensorDescription(
        key="remaining_weekly",
        icon="mdi:calendar-week",
        translation_key="remaining_weekly",
        name="Weekly remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.remaining_weekly,
        attrs_fn=lambda a: _pct_attrs(a.used_weekly, a.window_minutes_weekly, a),
    ),
    CodexRatesSensorDescription(
        key="remaining_monthly",
        icon="mdi:calendar-month",
        translation_key="remaining_monthly",
        name="Monthly remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.remaining_monthly,
        attrs_fn=lambda a: _pct_attrs(a.used_monthly, a.window_minutes_monthly, a),
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="used_5h",
        icon="mdi:percent",
        translation_key="used_5h",
        name="5h used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.used_5h,
        attrs_fn=lambda a: _used_pct_attrs(
            a.remaining_5h, a.window_minutes_5h, a
        ),
        used_percent=True,
    ),
    CodexRatesSensorDescription(
        key="used_weekly",
        icon="mdi:percent",
        translation_key="used_weekly",
        name="Weekly used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.used_weekly,
        attrs_fn=lambda a: _used_pct_attrs(
            a.remaining_weekly, a.window_minutes_weekly, a
        ),
        used_percent=True,
    ),
    CodexRatesSensorDescription(
        key="used_monthly",
        icon="mdi:percent",
        translation_key="used_monthly",
        name="Monthly used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.used_monthly,
        attrs_fn=lambda a: _used_pct_attrs(
            a.remaining_monthly, a.window_minutes_monthly, a
        ),
        used_percent=True,
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="reset_5h",
        icon="mdi:calendar-clock",
        translation_key="reset_5h",
        name="5h resets",
        value_fn=lambda a: a.reset_5h,
        attrs_fn=lambda a: _reset_attrs(a.reset_5h, a),
    ),
    CodexRatesSensorDescription(
        key="reset_weekly",
        icon="mdi:calendar-clock",
        translation_key="reset_weekly",
        name="Weekly resets",
        value_fn=lambda a: a.reset_weekly,
        attrs_fn=lambda a: _reset_attrs(a.reset_weekly, a),
    ),
    CodexRatesSensorDescription(
        key="reset_monthly",
        icon="mdi:calendar-clock",
        translation_key="reset_monthly",
        name="Monthly resets",
        value_fn=lambda a: a.reset_monthly,
        attrs_fn=lambda a: _reset_attrs(a.reset_monthly, a),
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="status",
        icon="mdi:help-circle-outline",
        translation_key="status",
        name="Status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_ICONS),
        value_fn=lambda a: a.status if a.status in STATUS_ICONS else "unknown",
        attrs_fn=_status_attrs,
    ),
    CodexRatesSensorDescription(
        key="remaining_spark_5h",
        icon="mdi:lightning-bolt",
        translation_key="remaining_spark_5h",
        name="Spark 5h remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.remaining_spark_5h,
        attrs_fn=lambda a: _pct_attrs(a.used_spark_5h, a.window_minutes_spark_5h, a),
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="remaining_spark_weekly",
        icon="mdi:lightning-bolt",
        translation_key="remaining_spark_weekly",
        name="Spark weekly remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.remaining_spark_weekly,
        attrs_fn=lambda a: _pct_attrs(
            a.used_spark_weekly, a.window_minutes_spark_weekly, a
        ),
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="used_spark_5h",
        icon="mdi:percent",
        translation_key="used_spark_5h",
        name="Spark 5h used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.used_spark_5h,
        attrs_fn=lambda a: _used_pct_attrs(
            a.remaining_spark_5h, a.window_minutes_spark_5h, a
        ),
        used_percent=True,
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="used_spark_weekly",
        icon="mdi:percent",
        translation_key="used_spark_weekly",
        name="Spark weekly used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda a: a.used_spark_weekly,
        attrs_fn=lambda a: _used_pct_attrs(
            a.remaining_spark_weekly, a.window_minutes_spark_weekly, a
        ),
        used_percent=True,
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="reset_spark_5h",
        icon="mdi:calendar-clock",
        translation_key="reset_spark_5h",
        name="Spark 5h resets",
        value_fn=lambda a: a.reset_spark_5h,
        attrs_fn=lambda a: _reset_attrs(a.reset_spark_5h, a),
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="reset_spark_weekly",
        icon="mdi:calendar-clock",
        translation_key="reset_spark_weekly",
        name="Spark weekly resets",
        value_fn=lambda a: a.reset_spark_weekly,
        attrs_fn=lambda a: _reset_attrs(a.reset_spark_weekly, a),
        codex_lb_only=True,
    ),
    CodexRatesSensorDescription(
        key="reset_credits",
        icon="mdi:restore",
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
        icon="mdi:card-account-details-outline",
        translation_key="plan_type",
        name="Plan",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.plan_type,
        rich=True,
    ),
    CodexRatesSensorDescription(
        key="credits_balance",
        icon="mdi:wallet-outline",
        translation_key="credits_balance",
        name="Credits balance",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.credits_balance,
        rich=True,
    ),
    CodexRatesSensorDescription(
        key="last_refresh",
        icon="mdi:update",
        translation_key="last_refresh",
        name="Last refresh",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.last_refresh_at,
        rich=True,
    ),
    CodexRatesSensorDescription(
        key="request_count",
        icon="mdi:counter",
        translation_key="request_count",
        name="Request count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.request_count,
        attrs_fn=_request_usage_attrs,
        rich=True,
    ),
)

_POOL_SENSOR_KEYS = frozenset(
    {
        "remaining_5h",
        "remaining_weekly",
        "remaining_monthly",
        "remaining_spark_5h",
        "remaining_spark_weekly",
        "used_5h",
        "used_weekly",
        "used_monthly",
        "used_spark_5h",
        "used_spark_weekly",
    }
)
_ACCOUNT_SENSOR_KEYS = frozenset(desc.key for desc in ACCOUNT_SENSORS)
_MONTHLY_SENSOR_KEYS = frozenset(
    {"remaining_monthly", "reset_monthly", "used_monthly"}
)


def snapshot_has_monthly(snapshot: ProviderSnapshot) -> bool:
    """True when any account reports a monthly remaining % or reset time."""
    return any(
        account.remaining_monthly is not None or account.reset_monthly is not None
        for account in snapshot.accounts
    )


def _include_description(
    description: CodexRatesSensorDescription,
    *,
    rich: bool,
    used_percent_sensors: bool = False,
    is_codex_lb: bool,
    has_monthly: bool,
) -> bool:
    if description.rich and not rich:
        return False
    if description.used_percent and not used_percent_sensors:
        return False
    if description.codex_lb_only and not is_codex_lb:
        return False
    return not (description.key in _MONTHLY_SENSOR_KEYS and not has_monthly)


def _account_supports_description(account: AccountQuota, key: str) -> bool:
    """Create quota entities only when this account actually reports that window."""
    fields = {
        "remaining_5h": account.remaining_5h,
        "remaining_weekly": account.remaining_weekly,
        "remaining_monthly": account.remaining_monthly,
        "used_5h": account.used_5h,
        "used_weekly": account.used_weekly,
        "used_monthly": account.used_monthly,
        "reset_5h": account.reset_5h,
        "reset_weekly": account.reset_weekly,
        "reset_monthly": account.reset_monthly,
        "remaining_spark_5h": account.remaining_spark_5h,
        "remaining_spark_weekly": account.remaining_spark_weekly,
        "used_spark_5h": account.used_spark_5h,
        "used_spark_weekly": account.used_spark_weekly,
        "reset_spark_5h": account.reset_spark_5h,
        "reset_spark_weekly": account.reset_spark_weekly,
        "request_count": account.request_count,
    }
    return key not in fields or fields[key] is not None


_POOL_NAMES = {
    "remaining_5h": "All accounts 5h remaining",
    "remaining_weekly": "All accounts weekly remaining",
    "remaining_monthly": "All accounts monthly remaining",
    "remaining_spark_5h": "All accounts Spark 5h remaining",
    "remaining_spark_weekly": "All accounts Spark weekly remaining",
    "used_5h": "All accounts 5h used",
    "used_weekly": "All accounts weekly used",
    "used_monthly": "All accounts monthly used",
    "used_spark_5h": "All accounts Spark 5h used",
    "used_spark_weekly": "All accounts Spark weekly used",
}


def _snapshot_sensors(coordinator, entry, snapshot):
    """The desired entities for one successful provider response."""
    rich = entry.options.get(CONF_RICH_SENSORS, DEFAULT_RICH_SENSORS)
    used_percent_sensors = entry.options.get(
        CONF_USED_PERCENT_SENSORS, DEFAULT_USED_PERCENT_SENSORS
    )
    is_codex_lb = entry.data.get(CONF_MODE) == MODE_CODEX_LB
    has_monthly = snapshot_has_monthly(snapshot)
    for account in snapshot.accounts:
        for description in ACCOUNT_SENSORS:
            if _include_description(
                description,
                rich=rich,
                used_percent_sensors=used_percent_sensors,
                is_codex_lb=is_codex_lb,
                has_monthly=has_monthly,
            ) and _account_supports_description(account, description.key):
                yield CodexAccountSensor(
                    coordinator, entry, account.account_id, description
                )
    if is_codex_lb and snapshot.pool is not None:
        for key, name in _POOL_NAMES.items():
            if key.startswith("used_") and not used_percent_sensors:
                continue
            window = getattr(snapshot.pool, _pool_aggregate_key(key))
            if window.sample_count:
                yield CodexPoolSensor(coordinator, entry, key, name)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Reconcile optional quota windows after each successful poll."""
    coordinator: CodexRatesCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.data is None:
        await coordinator.async_config_entry_first_refresh()

    entities: dict[str, SensorEntity] = {}
    pending: set[asyncio.Task] = set()
    lock = asyncio.Lock()

    async def _reconcile() -> None:
        async with lock:
            snapshot = coordinator.data
            if snapshot is None or not coordinator.last_update_success:
                return
            desired = {
                entity.unique_id: entity
                for entity in _snapshot_sensors(coordinator, entry, snapshot)
            }
            for unique_id in entities.keys() - desired.keys():
                entity = entities.pop(unique_id)
                # Disabled entities may never have been added to the platform.
                if entity.hass is None:
                    continue
                # Keep user disabled/hidden registry prefs when a quota window
                # disappears temporarily; only wipe the registry for gone accounts
                # or permanently unwanted keys.
                preserve = _unsupported_quota_window(
                    entry, snapshot, unique_id
                ) and _registry_entry_is_suppressed(
                    _registry_entry_for_unique_id(hass, entry.entry_id, unique_id)
                )
                await entity.async_remove(force_remove=not preserve)
            cleanup_orphan_devices(hass, entry, snapshot)
            added = [entity for key, entity in desired.items() if key not in entities]
            entities.update((entity.unique_id, entity) for entity in added)
            if added:
                async_add_entities(added)

    @callback
    def _on_coordinator_update() -> None:
        task = hass.async_create_task(_reconcile())
        pending.add(task)
        task.add_done_callback(pending.discard)

    @callback
    def _cancel_pending() -> None:
        for task in pending:
            task.cancel()

    await _reconcile()
    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))
    entry.async_on_unload(_cancel_pending)


def live_device_suffixes(entry: ConfigEntry, snapshot: ProviderSnapshot) -> set[str]:
    """Return device identifier suffixes that should remain for this entry."""
    live = {account.account_id for account in snapshot.accounts}
    if entry.data.get(CONF_MODE) == MODE_CODEX_LB:
        live.add(POOL_DEVICE_ID)
    return live


def allowed_sensor_keys(
    entry: ConfigEntry, snapshot: ProviderSnapshot | None = None
) -> set[str]:
    """Sensor keys that should exist for this config entry's mode/options/data."""
    rich = entry.options.get(CONF_RICH_SENSORS, DEFAULT_RICH_SENSORS)
    used_percent_sensors = entry.options.get(
        CONF_USED_PERCENT_SENSORS, DEFAULT_USED_PERCENT_SENSORS
    )
    is_codex_lb = entry.data.get(CONF_MODE) == MODE_CODEX_LB
    has_monthly = (
        snapshot_has_monthly(snapshot) if snapshot is not None else is_codex_lb
    )
    keys = {
        description.key
        for description in ACCOUNT_SENSORS
        if _include_description(
            description,
            rich=rich,
            used_percent_sensors=used_percent_sensors,
            is_codex_lb=is_codex_lb,
            has_monthly=has_monthly,
        )
    }
    if is_codex_lb:
        keys |= {"remaining_5h", "remaining_weekly"}
        if has_monthly:
            keys.add("remaining_monthly")
        if used_percent_sensors:
            keys |= {"used_5h", "used_weekly"}
            if has_monthly:
                keys.add("used_monthly")
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


def _registry_entry_is_suppressed(registry_entry: Any) -> bool:
    """True when the user disabled or hid the entity in the registry."""
    return (
        getattr(registry_entry, "disabled_by", None) is not None
        or getattr(registry_entry, "hidden_by", None) is not None
    )


def _unsupported_quota_window(
    entry: ConfigEntry, snapshot: ProviderSnapshot, unique_id: str
) -> bool:
    """True when the account/pool still exists but no longer reports this window."""
    account_id = account_id_from_unique_id(entry.entry_id, unique_id)
    sensor_key = sensor_key_from_unique_id(entry.entry_id, unique_id)
    if account_id is None or sensor_key is None:
        return False
    if account_id == POOL_DEVICE_ID and sensor_key in _POOL_SENSOR_KEYS:
        account_field = _pool_aggregate_key(sensor_key)
        return not any(
            getattr(item, account_field) is not None for item in snapshot.accounts
        )
    account = next(
        (item for item in snapshot.accounts if item.account_id == account_id),
        None,
    )
    return account is not None and not _account_supports_description(account, sensor_key)


def _registry_entry_for_unique_id(
    hass: HomeAssistant, entry_id: str, unique_id: str
) -> Any | None:
    try:
        entity_reg = er.async_get(hass)
    except Exception:  # noqa: BLE001 — stubs / early init
        return None
    if entity_reg is None:
        return None
    entities = getattr(entity_reg, "entities", None)
    if isinstance(entities, dict):
        for reg_entry in entities.values():
            if getattr(reg_entry, "unique_id", None) == unique_id:
                return reg_entry
    try:
        candidates = er.async_entries_for_config_entry(entity_reg, entry_id)
    except Exception:  # noqa: BLE001
        candidates = list(getattr(entity_reg, "_entries", []))
    for reg_entry in candidates:
        if getattr(reg_entry, "unique_id", None) == unique_id:
            return reg_entry
    return None


def cleanup_orphan_devices(
    hass: HomeAssistant, entry: ConfigEntry, snapshot: ProviderSnapshot
) -> list[str]:
    """Remove devices/entities that no longer belong to this entry.

    Drops:
    - devices for account_ids missing from the snapshot
    - entities for those accounts
    - entities whose sensor key is not created for the current mode/options/data
      (e.g. monthly sensors when the API never reports a monthly window)

    Returns removed device identifier suffixes (for tests).
    """
    live = live_device_suffixes(entry, snapshot)
    allowed_keys = allowed_sensor_keys(entry, snapshot)
    prefix = f"{entry.entry_id}_"
    removed: list[str] = []

    try:
        device_reg = dr.async_get(hass)
    except Exception:  # noqa: BLE001 — stubs / early init
        device_reg = None

    if device_reg is not None:
        try:
            devices = list(
                dr.async_entries_for_config_entry(device_reg, entry.entry_id)
            )
        except Exception:  # noqa: BLE001 — older HA / stubs
            devices = list(getattr(device_reg, "devices", {}).values())
        for device in devices:
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
        for entity in list(
            er.async_entries_for_config_entry(entity_reg, entry.entry_id)
        ):
            unique_id = entity.unique_id or ""
            account_id = account_id_from_unique_id(entry.entry_id, unique_id)
            sensor_key = sensor_key_from_unique_id(entry.entry_id, unique_id)
            if account_id is None or sensor_key is None:
                continue
            unsupported_window = _unsupported_quota_window(entry, snapshot, unique_id)
            if (
                account_id not in live
                or sensor_key not in allowed_keys
                or unsupported_window
            ):
                # Do not erase a user-disabled entity's preference/history merely
                # because this API response no longer exposes its quota window.
                if unsupported_window and _registry_entry_is_suppressed(entity):
                    continue
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


def _used_pct_attrs(
    remaining: float | None, window_minutes: int | None, account: AccountQuota
) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        ATTR_ACCOUNT_ID: account.account_id,
        ATTR_EMAIL: account.email,
    }
    if remaining is not None:
        attrs[ATTR_REMAINING_PERCENT] = remaining
    if window_minutes is not None:
        attrs[ATTR_WINDOW_MINUTES] = window_minutes
    return attrs


def _invert_percent(value: float | None) -> float | None:
    """Convert remaining % aggregate stats to used % (and the reverse)."""
    if value is None:
        return None
    return round(100.0 - float(value), 2)


def _account_from_data(
    data: ProviderSnapshot | None, account_id: str
) -> AccountQuota | None:
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
    def name(self) -> str | None:
        account = _account_from_data(self.coordinator.data, self.account_id)
        if account is not None:
            dynamic_name = _account_window_name(account, self.entity_description.key)
            if dynamic_name is not None:
                return dynamic_name
        return self.entity_description.name

    @property
    def icon(self) -> str | None:
        if self.entity_description.key == "status":
            account = _account_from_data(self.coordinator.data, self.account_id)
            return STATUS_ICONS.get(
                account.status if account else "unknown", STATUS_ICONS["unknown"]
            )
        return self.entity_description.icon

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
        value = self.entity_description.value_fn(account)  # type: ignore[attr-defined]
        if _is_reset_window_key(self.entity_description.key):
            return _format_reset_display(
                value if isinstance(value, datetime) else None, self._entry
            )
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        account = _account_from_data(self.coordinator.data, self.account_id)
        if account is None:
            return None
        attrs_fn = self.entity_description.attrs_fn  # type: ignore[attr-defined]
        if attrs_fn is None:
            return {ATTR_ACCOUNT_ID: account.account_id, ATTR_EMAIL: account.email}
        attrs = attrs_fn(account)
        if "spark" in self.entity_description.key:
            attrs["quota_model"] = "gpt-5.3-codex-spark"
        return attrs


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
        self._fallback_name = name
        self._attr_icon = "mdi:lightning-bolt" if "spark" in key else "mdi:gauge"
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
        aggregate_key = _pool_aggregate_key(self._key)
        if aggregate_key == "remaining_5h":
            return data.pool.remaining_5h
        if aggregate_key == "remaining_weekly":
            return data.pool.remaining_weekly
        if aggregate_key == "remaining_spark_5h":
            return data.pool.remaining_spark_5h
        if aggregate_key == "remaining_spark_weekly":
            return data.pool.remaining_spark_weekly
        return data.pool.remaining_monthly

    @property
    def name(self) -> str | None:
        window = self._window()
        if window is None:
            return self._fallback_name
        return _pool_window_name(self._key, window, self._fallback_name)

    @property
    def native_value(self) -> float | None:
        window = self._window()
        if window is None:
            return None
        if self._key.startswith("used_"):
            return _invert_percent(window.mean)
        return window.mean

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        window = self._window()
        if data is None or data.pool is None or window is None:
            return None
        used = self._key.startswith("used_")
        attrs: dict[str, Any] = {
            ATTR_MIN: _invert_percent(window.max) if used else window.min,
            ATTR_MAX: _invert_percent(window.min) if used else window.max,
            ATTR_ACCOUNT_COUNT: data.pool.account_count,
            ATTR_ACTIVE_COUNT: data.pool.active_count,
            "sample_count": window.sample_count,
            "missing_quota_count": data.pool.account_count - window.sample_count,
        }
        if window.window_minutes is not None:
            attrs[ATTR_WINDOW_MINUTES] = window.window_minutes
        if window.by_minutes:
            attrs[ATTR_BY_MINUTES] = {
                str(minutes): (
                    _invert_percent(mean) if used else mean
                )
                for minutes, mean in window.by_minutes.items()
            }
        if "spark" in self._key:
            attrs["quota_model"] = "gpt-5.3-codex-spark"
            attrs["weighting_method"] = (
                "account_plan_capacity"
                if window.weighting_method == "capacity_credits"
                else window.weighting_method
            )
        else:
            if window.weighted_capacity is not None:
                attrs["capacity_credits"] = window.weighted_capacity
            attrs["weighting_method"] = window.weighting_method
        attrs["missing_weight_count"] = window.missing_weight_count
        return attrs