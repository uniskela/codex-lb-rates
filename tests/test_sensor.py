"""Tests for quota presentation, optional windows and entity lifecycle."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from custom_components.codex_rates.const import (
    CONF_MODE,
    DOMAIN,
    MODE_CHATGPT,
    MODE_CODEX_LB,
)
from custom_components.codex_rates.models import AccountQuota, ProviderSnapshot
from custom_components.codex_rates.sensor import (
    ACCOUNT_SENSORS,
    _include_description,
    account_id_from_unique_id,
    allowed_sensor_keys,
    cleanup_orphan_devices,
    live_device_suffixes,
    sensor_key_from_unique_id,
)


def test_reset_display_toggle_countdown_and_absolute(monkeypatch) -> None:
    from homeassistant.util import dt as dt_util

    import custom_components.codex_rates.models as models_mod
    from custom_components.codex_rates.const import (
        CONF_RESET_DISPLAY,
        RESET_DISPLAY_ABSOLUTE,
        RESET_DISPLAY_COUNTDOWN,
    )
    from custom_components.codex_rates.models import format_reset_countdown
    from custom_components.codex_rates.sensor import (
        ACCOUNT_SENSORS,
        CodexAccountSensor,
        _absolute_reset,
        _format_reset_display,
        _reset_attrs,
    )

    monkeypatch.setattr(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("Asia/Tbilisi"))
    when = datetime(2026, 9, 19, 23, 30, tzinfo=timezone.utc)
    now = datetime(2026, 9, 19, 20, 0, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(models_mod, "datetime", _FixedDateTime)

    assert _absolute_reset(when) == "2026-09-20 03:30"
    assert format_reset_countdown(when, now=now) == "4h"
    attrs = _reset_attrs(when, AccountQuota(account_id="a"))
    assert attrs["resets_at"] == "2026-09-19T23:30:00+00:00"
    assert attrs["reset_timezone"] == "Asia/Tbilisi"

    absolute_entry = SimpleNamespace(
        entry_id="test", options={CONF_RESET_DISPLAY: RESET_DISPLAY_ABSOLUTE}
    )
    countdown_entry = SimpleNamespace(
        entry_id="test", options={CONF_RESET_DISPLAY: RESET_DISPLAY_COUNTDOWN}
    )
    default_entry = SimpleNamespace(entry_id="test", options={})
    assert _format_reset_display(when, absolute_entry) == "2026-09-20 03:30"
    assert _format_reset_display(when, countdown_entry) == "4h"
    assert _format_reset_display(when, default_entry) == "4h"

    description = next(d for d in ACCOUNT_SENSORS if d.key == "reset_5h")
    account = AccountQuota(account_id="a", reset_5h=when)
    coordinator = SimpleNamespace(data=ProviderSnapshot(accounts=[account]))
    assert (
        CodexAccountSensor(coordinator, absolute_entry, "a", description).native_value
        == "2026-09-20 03:30"
    )
    assert (
        CodexAccountSensor(coordinator, countdown_entry, "a", description).native_value
        == "4h"
    )
    assert (
        CodexAccountSensor(coordinator, default_entry, "a", description).native_value
        == "4h"
    )


def test_status_keeps_machine_codes_and_distinct_action_icons() -> None:
    from custom_components.codex_rates.sensor import STATUS_ICONS, CodexAccountSensor

    description = next(d for d in ACCOUNT_SENSORS if d.key == "status")
    entry = SimpleNamespace(entry_id="test")
    account = AccountQuota(account_id="a")
    coordinator = SimpleNamespace(data=ProviderSnapshot(accounts=[account]))
    sensor = CodexAccountSensor(coordinator, entry, "a", description)
    for status in (
        "active",
        "rate_limited",
        "quota_exceeded",
        "paused",
        "reauth_required",
        "deactivated",
    ):
        account.status = status
        assert sensor.native_value == status
        assert sensor.icon == STATUS_ICONS[status]
        assert sensor.icon != STATUS_ICONS["unknown"]
    account.status = "future_server_status"
    assert sensor.native_value == "unknown"
    assert sensor.extra_state_attributes["raw_status"] == "future_server_status"
    assert all(d.icon and d.icon.startswith("mdi:") for d in ACCOUNT_SENSORS)


@pytest.mark.asyncio
async def test_optional_windows_disappear_and_return_without_duplicate_entities(
    monkeypatch,
) -> None:
    import custom_components.codex_rates.sensor as sensor_mod
    from custom_components.codex_rates.models import compute_pool_aggregate

    account = AccountQuota(account_id="changing", remaining_weekly=40)
    neighbour = AccountQuota(account_id="unchanged", remaining_weekly=70)
    accounts = [account, neighbour]
    listeners = []
    unload = []
    tasks = []
    coordinator = SimpleNamespace(last_update_success=True)
    coordinator.async_add_listener = lambda callback: (
        listeners.append(callback),
        lambda: None,
    )[1]
    coordinator.data = ProviderSnapshot(
        accounts=accounts, pool=compute_pool_aggregate(accounts)
    )
    hass = SimpleNamespace(
        data={DOMAIN: {"entry": coordinator}}, entities={}, removed=[]
    )

    def create_task(coro):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    hass.async_create_task = create_task
    entry = SimpleNamespace(
        entry_id="entry",
        data={CONF_MODE: MODE_CODEX_LB},
        options={},
        async_on_unload=unload.append,
    )

    def add_entities(entities):
        for entity in entities:
            assert entity.unique_id not in hass.entities
            entity.hass = hass
            hass.entities[entity.unique_id] = entity

    monkeypatch.setattr(sensor_mod, "cleanup_orphan_devices", lambda *args: None)
    await sensor_mod.async_setup_entry(hass, entry, add_entities)
    unchanged = hass.entities["entry_unchanged_remaining_weekly"]
    initial = set(hass.entities)

    async def poll():
        coordinator.data = ProviderSnapshot(
            accounts=accounts, pool=compute_pool_aggregate(accounts)
        )
        listeners[0]()
        await asyncio.gather(*tasks)

    for _ in range(2):
        account.remaining_5h = 0
        account.reset_5h = datetime(2026, 9, 20, tzinfo=timezone.utc)
        account.remaining_spark_weekly = 0
        await poll()
        assert {
            "entry_changing_remaining_5h",
            "entry_changing_reset_5h",
            "entry_pool_remaining_5h",
            "entry_changing_remaining_spark_weekly",
            "entry_pool_remaining_spark_weekly",
        } <= hass.entities.keys()
        assert "entry_unchanged_remaining_spark_weekly" not in hass.entities
        assert hass.entities["entry_unchanged_remaining_weekly"] is unchanged
        account.remaining_5h = account.reset_5h = account.remaining_spark_weekly = None
        coordinator.last_update_success = False
        measured = set(hass.entities)
        await poll()
        assert set(hass.entities) == measured  # A failed poll must not prune.
        coordinator.last_update_success = True
        await poll()
        assert set(hass.entities) == initial
    # Removing and re-adding an account must recover its stable quota identities too.
    accounts.remove(account)
    await poll()
    assert not any(key.startswith("entry_changing_") for key in hass.entities)
    accounts.append(account)
    await poll()
    assert set(hass.entities) == initial
    for callback in unload:
        callback()


def test_chatgpt_excludes_monthly_includes_reset_credits() -> None:
    keys = {
        d.key
        for d in ACCOUNT_SENSORS
        if _include_description(d, rich=False, is_codex_lb=False, has_monthly=False)
    }
    assert "remaining_monthly" not in keys
    assert "reset_monthly" not in keys
    assert "reset_credits" in keys
    assert "remaining_5h" in keys
    assert "plan_type" not in keys  # rich


def test_codex_lb_includes_monthly_when_present() -> None:
    keys = {
        d.key
        for d in ACCOUNT_SENSORS
        if _include_description(d, rich=False, is_codex_lb=True, has_monthly=True)
    }
    assert "remaining_monthly" in keys
    assert "reset_monthly" in keys
    assert "reset_credits" in keys


def test_codex_lb_excludes_monthly_when_absent() -> None:
    keys = {
        d.key
        for d in ACCOUNT_SENSORS
        if _include_description(d, rich=False, is_codex_lb=True, has_monthly=False)
    }
    assert "remaining_monthly" not in keys
    assert "reset_monthly" not in keys


def test_allowed_sensor_keys_chatgpt_drops_monthly() -> None:
    entry = SimpleNamespace(data={CONF_MODE: MODE_CHATGPT}, options={})
    snapshot = ProviderSnapshot(accounts=[AccountQuota(account_id="acc1")])
    keys = allowed_sensor_keys(entry, snapshot)  # type: ignore[arg-type]
    assert "remaining_monthly" not in keys
    assert "reset_monthly" not in keys
    assert "reset_credits" in keys
    assert "remaining_5h" in keys


def test_allowed_sensor_keys_lb_drops_empty_monthly() -> None:
    entry = SimpleNamespace(data={CONF_MODE: MODE_CODEX_LB}, options={})
    snapshot = ProviderSnapshot(accounts=[AccountQuota(account_id="acc1")])
    keys = allowed_sensor_keys(entry, snapshot)  # type: ignore[arg-type]
    assert "remaining_monthly" not in keys
    assert "reset_monthly" not in keys
    assert "remaining_5h" in keys


def test_account_id_from_unique_id() -> None:
    entry_id = "entry1"
    assert (
        account_id_from_unique_id(entry_id, f"{entry_id}_acc_abc_remaining_5h")
        == "acc_abc"
    )
    assert (
        account_id_from_unique_id(entry_id, f"{entry_id}_user@x.com_reset_weekly")
        == "user@x.com"
    )
    assert (
        account_id_from_unique_id(entry_id, f"{entry_id}_pool_remaining_5h") == "pool"
    )
    assert account_id_from_unique_id(entry_id, "other_entry_acc_remaining_5h") is None
    assert (
        sensor_key_from_unique_id(entry_id, f"{entry_id}_acc_abc_remaining_monthly")
        == "remaining_monthly"
    )


def test_live_device_suffixes() -> None:
    snapshot = ProviderSnapshot(
        accounts=[AccountQuota(account_id="acc_1"), AccountQuota(account_id="acc_2")]
    )
    lb_entry = SimpleNamespace(data={CONF_MODE: MODE_CODEX_LB}, entry_id="e1")
    cg_entry = SimpleNamespace(data={CONF_MODE: MODE_CHATGPT}, entry_id="e2")
    assert live_device_suffixes(lb_entry, snapshot) == {"acc_1", "acc_2", "pool"}  # type: ignore[arg-type]
    assert live_device_suffixes(cg_entry, snapshot) == {"acc_1", "acc_2"}  # type: ignore[arg-type]


def _patch_registries(sensor_mod, device_reg, entity_reg):
    original_dr_get = sensor_mod.dr.async_get
    original_dr_entries = getattr(sensor_mod.dr, "async_entries_for_config_entry", None)
    original_er_get = sensor_mod.er.async_get
    original_er_entries = sensor_mod.er.async_entries_for_config_entry
    sensor_mod.dr.async_get = lambda _hass: device_reg
    sensor_mod.dr.async_entries_for_config_entry = lambda registry, entry_id: list(
        getattr(registry, "devices", {}).values()
    )
    sensor_mod.er.async_get = lambda _hass: entity_reg
    sensor_mod.er.async_entries_for_config_entry = lambda registry, entry_id: (
        registry._entries
    )
    return original_dr_get, original_dr_entries, original_er_get, original_er_entries


def test_cleanup_orphan_devices_removes_stale() -> None:
    class FakeDevice:
        def __init__(self, device_id: str, ident: str) -> None:
            self.id = device_id
            self.identifiers = {(DOMAIN, ident)}

    class FakeDeviceRegistry:
        def __init__(self) -> None:
            self.devices = {
                "d_live": FakeDevice("d_live", "entry1_acc_live"),
                "d_stale": FakeDevice("d_stale", "entry1_old@email.com"),
                "d_other": FakeDevice("d_other", "other_entry_acc"),
            }
            self.removed: list[str] = []

        def async_remove_device(self, device_id: str) -> None:
            self.removed.append(device_id)
            self.devices.pop(device_id, None)

    class FakeEntity:
        def __init__(self, entity_id: str, unique_id: str) -> None:
            self.entity_id = entity_id
            self.unique_id = unique_id

    class FakeEntityRegistry:
        def __init__(self) -> None:
            self.removed: list[str] = []
            self._entries = [
                FakeEntity("sensor.a", "entry1_acc_live_remaining_5h"),
                FakeEntity("sensor.b", "entry1_old@email.com_remaining_5h"),
            ]

        def async_remove(self, entity_id: str) -> None:
            self.removed.append(entity_id)

    entry = SimpleNamespace(
        entry_id="entry1", data={CONF_MODE: MODE_CODEX_LB}, options={}
    )
    snapshot = ProviderSnapshot(
        accounts=[AccountQuota(account_id="acc_live", remaining_5h=50)]
    )
    hass = SimpleNamespace()
    device_reg = FakeDeviceRegistry()
    entity_reg = FakeEntityRegistry()

    import custom_components.codex_rates.sensor as sensor_mod

    originals = _patch_registries(sensor_mod, device_reg, entity_reg)
    try:
        removed = cleanup_orphan_devices(hass, entry, snapshot)  # type: ignore[arg-type]
    finally:
        (
            sensor_mod.dr.async_get,
            sensor_mod.dr.async_entries_for_config_entry,
            sensor_mod.er.async_get,
            sensor_mod.er.async_entries_for_config_entry,
        ) = originals

    assert removed == ["old@email.com"]
    assert "d_stale" in device_reg.removed
    assert "d_live" not in device_reg.removed
    assert "d_other" not in device_reg.removed
    assert entity_reg.removed == ["sensor.b"]


def test_cleanup_removes_chatgpt_monthly_entities() -> None:
    class FakeEntity:
        def __init__(self, entity_id: str, unique_id: str) -> None:
            self.entity_id = entity_id
            self.unique_id = unique_id

    class FakeEntityRegistry:
        def __init__(self) -> None:
            self.removed: list[str] = []
            self._entries = [
                FakeEntity("sensor.ok", "entry1_acc1_remaining_5h"),
                FakeEntity("sensor.monthly", "entry1_acc1_remaining_monthly"),
                FakeEntity("sensor.reset_m", "entry1_acc1_reset_monthly"),
            ]

        def async_remove(self, entity_id: str) -> None:
            self.removed.append(entity_id)

    class FakeDeviceRegistry:
        def __init__(self):
            self.devices = {}

        def async_remove_device(self, device_id: str) -> None:
            raise AssertionError("should not remove devices")

    entry = SimpleNamespace(
        entry_id="entry1", data={CONF_MODE: MODE_CHATGPT}, options={}
    )
    snapshot = ProviderSnapshot(
        accounts=[AccountQuota(account_id="acc1", remaining_5h=50)]
    )
    hass = SimpleNamespace()
    entity_reg = FakeEntityRegistry()
    device_reg = FakeDeviceRegistry()

    import custom_components.codex_rates.sensor as sensor_mod

    originals = _patch_registries(sensor_mod, device_reg, entity_reg)
    try:
        cleanup_orphan_devices(hass, entry, snapshot)  # type: ignore[arg-type]
    finally:
        (
            sensor_mod.dr.async_get,
            sensor_mod.dr.async_entries_for_config_entry,
            sensor_mod.er.async_get,
            sensor_mod.er.async_entries_for_config_entry,
        ) = originals

    assert set(entity_reg.removed) == {"sensor.monthly", "sensor.reset_m"}


def test_cleanup_removes_lb_monthly_when_api_omits_monthly() -> None:
    class FakeEntity:
        def __init__(self, entity_id: str, unique_id: str) -> None:
            self.entity_id = entity_id
            self.unique_id = unique_id

    class FakeEntityRegistry:
        def __init__(self) -> None:
            self.removed: list[str] = []
            self._entries = [
                FakeEntity("sensor.ok", "entry1_acc1_remaining_5h"),
                FakeEntity("sensor.monthly", "entry1_acc1_remaining_monthly"),
                FakeEntity("sensor.pool_m", "entry1_pool_remaining_monthly"),
            ]

        def async_remove(self, entity_id: str) -> None:
            self.removed.append(entity_id)

    class FakeDeviceRegistry:
        def __init__(self):
            self.devices = {}

        def async_remove_device(self, device_id: str) -> None:
            raise AssertionError("should not remove devices")

    entry = SimpleNamespace(
        entry_id="entry1", data={CONF_MODE: MODE_CODEX_LB}, options={}
    )
    snapshot = ProviderSnapshot(
        accounts=[AccountQuota(account_id="acc1", remaining_5h=50)]
    )
    hass = SimpleNamespace()
    entity_reg = FakeEntityRegistry()
    device_reg = FakeDeviceRegistry()

    import custom_components.codex_rates.sensor as sensor_mod

    originals = _patch_registries(sensor_mod, device_reg, entity_reg)
    try:
        cleanup_orphan_devices(hass, entry, snapshot)  # type: ignore[arg-type]
    finally:
        (
            sensor_mod.dr.async_get,
            sensor_mod.dr.async_entries_for_config_entry,
            sensor_mod.er.async_get,
            sensor_mod.er.async_entries_for_config_entry,
        ) = originals

    assert set(entity_reg.removed) == {"sensor.monthly", "sensor.pool_m"}
