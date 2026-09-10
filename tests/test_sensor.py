"""Tests for sensor helpers (countdown wiring, orphan cleanup)."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.codex_rates.const import CONF_MODE, DOMAIN, MODE_CODEX_LB, MODE_CHATGPT
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


def test_chatgpt_excludes_monthly_includes_reset_credits() -> None:
    keys = {
        d.key
        for d in ACCOUNT_SENSORS
        if _include_description(
            d, rich=False, is_codex_lb=False, has_monthly=False
        )
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
    assert account_id_from_unique_id(entry_id, f"{entry_id}_pool_remaining_5h") == "pool"
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
    sensor_mod.dr.async_entries_for_config_entry = (
        lambda registry, entry_id: list(getattr(registry, "devices", {}).values())
    )
    sensor_mod.er.async_get = lambda _hass: entity_reg
    sensor_mod.er.async_entries_for_config_entry = (
        lambda registry, entry_id: registry._entries
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

    entry = SimpleNamespace(entry_id="entry1", data={CONF_MODE: MODE_CODEX_LB}, options={})
    snapshot = ProviderSnapshot(accounts=[AccountQuota(account_id="acc_live")])
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
        devices: dict = {}

        def async_remove_device(self, device_id: str) -> None:
            raise AssertionError("should not remove devices")

    entry = SimpleNamespace(entry_id="entry1", data={CONF_MODE: MODE_CHATGPT}, options={})
    snapshot = ProviderSnapshot(accounts=[AccountQuota(account_id="acc1")])
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
        devices: dict = {}

        def async_remove_device(self, device_id: str) -> None:
            raise AssertionError("should not remove devices")

    entry = SimpleNamespace(entry_id="entry1", data={CONF_MODE: MODE_CODEX_LB}, options={})
    snapshot = ProviderSnapshot(accounts=[AccountQuota(account_id="acc1")])
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
