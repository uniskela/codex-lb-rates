"""Tests for support diagnostics and coordinator poll freshness."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from custom_components.codex_rates.const import CONF_POLL_INTERVAL, DOMAIN
from custom_components.codex_rates.coordinator import CodexRatesCoordinator
from custom_components.codex_rates.diagnostics import async_get_config_entry_diagnostics
from custom_components.codex_rates.models import AccountQuota, ProviderSnapshot


@pytest.mark.asyncio
async def test_diagnostics_include_reset_timing_and_poll_freshness(monkeypatch) -> None:
    """Support diagnostics should expose raw reset timing and HA poll freshness."""
    import custom_components.codex_rates.diagnostics as diagnostics_mod

    now = datetime(2026, 9, 16, 12, 30, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(diagnostics_mod, "datetime", _FixedDateTime, raising=False)

    account = AccountQuota(
        account_id="acc",
        email="user@example.com",
        remaining_5h=72,
        remaining_weekly=61,
        reset_5h=datetime(2026, 9, 16, 14, 0, tzinfo=timezone.utc),
        reset_weekly=datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc),
        reset_monthly=datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc),
        window_minutes_5h=300,
        window_minutes_weekly=10080,
        window_minutes_monthly=43200,
        last_refresh_at=datetime(2026, 9, 16, 12, 25, tzinfo=timezone.utc),
        reset_spark_5h=datetime(2026, 9, 16, 13, 30, tzinfo=timezone.utc),
        reset_spark_weekly=datetime(2026, 9, 19, 0, 0, tzinfo=timezone.utc),
        window_minutes_spark_5h=300,
        window_minutes_spark_weekly=10080,
    )
    coordinator = SimpleNamespace(
        data=ProviderSnapshot(accounts=[account]),
        last_update_success=True,
        poll_interval_seconds=60,
        last_successful_poll_at=datetime(2026, 9, 16, 12, 29, tzinfo=timezone.utc),
    )
    entry = SimpleNamespace(
        entry_id="entry",
        title="Codex-LB",
        data={},
        options={},
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry": coordinator}})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["coordinator"] == {
        "last_update_success": True,
        "poll_interval_seconds": 60,
        "last_successful_poll_at": "2026-09-16T12:29:00+00:00",
    }

    diag = result["accounts"][0]
    assert diag["reset_5h"] == "2026-09-16T14:00:00+00:00"
    assert diag["reset_weekly"] == "2026-09-20T00:00:00+00:00"
    assert diag["reset_monthly"] == "2026-10-01T00:00:00+00:00"
    assert diag["window_minutes_5h"] == 300
    assert diag["window_minutes_weekly"] == 10080
    assert diag["window_minutes_monthly"] == 43200
    assert diag["last_refresh_at"] == "2026-09-16T12:25:00+00:00"
    assert diag["reset_spark_5h"] == "2026-09-16T13:30:00+00:00"
    assert diag["reset_spark_weekly"] == "2026-09-19T00:00:00+00:00"
    assert diag["window_minutes_spark_5h"] == 300
    assert diag["window_minutes_spark_weekly"] == 10080
    assert diag["reset_5h_remaining_seconds"] == 5400
    assert diag["reset_5h_remaining_hours"] == 1.5


@pytest.mark.asyncio
async def test_coordinator_records_last_successful_poll_time(monkeypatch) -> None:
    """A successful provider fetch should stamp HA-side poll freshness."""
    import custom_components.codex_rates.coordinator as coordinator_mod

    now = datetime(2026, 9, 16, 12, 30, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(coordinator_mod, "datetime", _FixedDateTime, raising=False)

    snapshot = ProviderSnapshot(accounts=[AccountQuota(account_id="acc")])

    class _Provider:
        async def async_fetch(self):
            return snapshot

    entry = SimpleNamespace(options={}, data={CONF_POLL_INTERVAL: 60})
    coordinator = CodexRatesCoordinator(SimpleNamespace(), entry)
    coordinator._provider = _Provider()

    result = await coordinator._async_update_data()

    assert result is snapshot
    assert coordinator.poll_interval_seconds == 60
    assert coordinator.last_successful_poll_at == now
