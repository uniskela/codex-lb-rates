"""Regression coverage for server-reported quota window durations."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from custom_components.codex_rates.const import CONF_MODE, MODE_CODEX_LB
from custom_components.codex_rates.models import AccountQuota, ProviderSnapshot, compute_pool_aggregate
from custom_components.codex_rates.sensor import ACCOUNT_SENSORS, CodexAccountSensor, CodexPoolSensor


def _description(key: str):
    return next(description for description in ACCOUNT_SENSORS if description.key == key)


def test_account_window_labels_follow_server_duration_without_changing_unique_ids() -> None:
    """A 24h primary window must not still present itself as a 5h quota."""
    reset = datetime(2026, 9, 17, 14, 0, tzinfo=timezone.utc)
    account = AccountQuota(
        account_id="acc",
        remaining_5h=84,
        remaining_weekly=12,
        reset_5h=reset,
        reset_weekly=reset,
        window_minutes_5h=24 * 60,
        window_minutes_weekly=7 * 24 * 60,
    )
    coordinator = SimpleNamespace(data=ProviderSnapshot(accounts=[account]))
    entry = SimpleNamespace(entry_id="entry", options={})

    primary_remaining = CodexAccountSensor(
        coordinator, entry, "acc", _description("remaining_5h")
    )
    primary_reset = CodexAccountSensor(
        coordinator, entry, "acc", _description("reset_5h")
    )
    secondary_remaining = CodexAccountSensor(
        coordinator, entry, "acc", _description("remaining_weekly")
    )

    assert getattr(primary_remaining, "name", None) == "Daily remaining"
    assert getattr(primary_reset, "name", None) == "Daily resets"
    assert getattr(secondary_remaining, "name", None) == "Weekly remaining"

    # Keep the old identity keys so dashboards/automations survive the display-name fix.
    assert primary_remaining.unique_id == "entry_acc_remaining_5h"
    assert primary_reset.unique_id == "entry_acc_reset_5h"


def test_five_hour_labels_are_preserved_when_server_reports_300_minutes() -> None:
    account = AccountQuota(
        account_id="acc",
        remaining_5h=50,
        window_minutes_5h=5 * 60,
    )
    coordinator = SimpleNamespace(data=ProviderSnapshot(accounts=[account]))
    entry = SimpleNamespace(entry_id="entry", options={})

    sensor = CodexAccountSensor(
        coordinator, entry, "acc", _description("remaining_5h")
    )

    assert getattr(sensor, "name", None) == "5h remaining"


def test_account_label_keeps_legacy_name_when_duration_is_missing() -> None:
    account = AccountQuota(account_id="acc", remaining_5h=50)
    coordinator = SimpleNamespace(data=ProviderSnapshot(accounts=[account]))
    entry = SimpleNamespace(entry_id="entry", options={})

    sensor = CodexAccountSensor(
        coordinator, entry, "acc", _description("remaining_5h")
    )

    assert getattr(sensor, "name", None) == "5h remaining"


def test_pool_label_uses_uniform_reported_window_duration() -> None:
    account = AccountQuota(
        account_id="acc",
        status="active",
        remaining_5h=84,
        window_minutes_5h=24 * 60,
    )
    snapshot = ProviderSnapshot(
        accounts=[account],
        pool=compute_pool_aggregate([account]),
    )
    coordinator = SimpleNamespace(data=snapshot)
    entry = SimpleNamespace(
        entry_id="entry",
        data={CONF_MODE: MODE_CODEX_LB},
        options={},
    )

    sensor = CodexPoolSensor(
        coordinator,
        entry,
        "remaining_5h",
        "All accounts 5h remaining",
    )

    assert getattr(sensor, "name", None) == "All accounts daily remaining"
    assert sensor.unique_id == "entry_pool_remaining_5h"


def test_pool_label_is_generic_when_accounts_report_mixed_durations() -> None:
    accounts = [
        AccountQuota(
            account_id="five",
            status="active",
            remaining_5h=80,
            window_minutes_5h=5 * 60,
        ),
        AccountQuota(
            account_id="daily",
            status="active",
            remaining_5h=60,
            window_minutes_5h=24 * 60,
        ),
    ]
    snapshot = ProviderSnapshot(
        accounts=accounts,
        pool=compute_pool_aggregate(accounts),
    )
    coordinator = SimpleNamespace(data=snapshot)
    entry = SimpleNamespace(
        entry_id="entry",
        data={CONF_MODE: MODE_CODEX_LB},
        options={},
    )
    sensor = CodexPoolSensor(
        coordinator,
        entry,
        "remaining_5h",
        "All accounts 5h remaining",
    )

    assert snapshot.pool is not None
    assert snapshot.pool.remaining_5h.window_minutes is None
    assert snapshot.pool.remaining_5h.by_minutes
    assert getattr(sensor, "name", None) == "All accounts primary remaining"


def test_pool_label_keeps_legacy_name_when_duration_is_unknown() -> None:
    account = AccountQuota(account_id="acc", status="active", remaining_5h=84)
    snapshot = ProviderSnapshot(
        accounts=[account],
        pool=compute_pool_aggregate([account]),
    )
    coordinator = SimpleNamespace(data=snapshot)
    entry = SimpleNamespace(
        entry_id="entry",
        data={CONF_MODE: MODE_CODEX_LB},
        options={},
    )
    sensor = CodexPoolSensor(
        coordinator,
        entry,
        "remaining_5h",
        "All accounts 5h remaining",
    )

    assert getattr(sensor, "name", None) == "All accounts 5h remaining"
