"""Tests for support diagnostics and coordinator poll freshness."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from custom_components.codex_rates.const import (
    CONF_MODE,
    CONF_POLL_INTERVAL,
    DOMAIN,
    MODE_CHATGPT,
    MODE_CODEX_LB,
)
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
        rate_limit_cooldown_until=None,
        last_rate_limit_at=None,
        last_rate_limit_retry_after=None,
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
        "rate_limit_active": False,
        "rate_limit_cooldown_until": None,
        "last_rate_limit_at": None,
        "last_rate_limit_retry_after": None,
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

    entry = SimpleNamespace(
        entry_id="entry",
        options={},
        data={CONF_POLL_INTERVAL: 60, CONF_MODE: MODE_CODEX_LB},
    )
    coordinator = CodexRatesCoordinator(SimpleNamespace(data={}), entry)
    coordinator._provider = _Provider()

    result = await coordinator._async_update_data()

    assert result is snapshot
    assert coordinator.poll_interval_seconds == 60
    assert coordinator.last_successful_poll_at == now
    assert snapshot.accounts[0].last_refresh_at is None


@pytest.mark.asyncio
async def test_coordinator_applies_cooldown_on_rate_limit(monkeypatch) -> None:
    """HTTP 429 should stretch the poll interval and surface a clear UpdateFailed."""
    import custom_components.codex_rates.coordinator as coordinator_mod
    from custom_components.codex_rates.exceptions import CodexRatesRateLimitError
    from homeassistant.helpers.update_coordinator import UpdateFailed

    now = datetime(2026, 9, 16, 12, 30, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(coordinator_mod, "datetime", _FixedDateTime, raising=False)

    class _Provider:
        async def async_fetch(self):
            raise CodexRatesRateLimitError("limited", retry_after=120)

    entry = SimpleNamespace(entry_id="entry", options={}, data={CONF_POLL_INTERVAL: 60})
    coordinator = CodexRatesCoordinator(SimpleNamespace(data={}), entry)
    coordinator._provider = _Provider()

    with pytest.raises(UpdateFailed) as excinfo:
        await coordinator._async_update_data()

    message = str(excinfo.value)
    assert "HTTP rate limited" in message
    assert "rate_limited" in message  # clarifies distinction from account status
    assert coordinator.rate_limit_cooldown_until == datetime(
        2026, 9, 16, 12, 32, tzinfo=timezone.utc
    )
    assert coordinator.last_rate_limit_retry_after == 120
    assert coordinator.update_interval.total_seconds() == 120


@pytest.mark.asyncio
async def test_coordinator_skips_provider_during_cooldown(monkeypatch) -> None:
    """While cooldown is active, do not call the provider again."""
    import custom_components.codex_rates.coordinator as coordinator_mod
    from homeassistant.helpers.update_coordinator import UpdateFailed

    now = datetime(2026, 9, 16, 12, 30, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(coordinator_mod, "datetime", _FixedDateTime, raising=False)

    calls = {"n": 0}

    class _Provider:
        async def async_fetch(self):
            calls["n"] += 1
            raise AssertionError("provider should not be called during cooldown")

    entry = SimpleNamespace(entry_id="entry", options={}, data={CONF_POLL_INTERVAL: 60})
    coordinator = CodexRatesCoordinator(SimpleNamespace(data={}), entry)
    coordinator._provider = _Provider()
    coordinator.rate_limit_cooldown_until = now.replace(minute=35)
    coordinator.last_rate_limit_at = now.replace(minute=29)
    coordinator.last_rate_limit_retry_after = 360

    with pytest.raises(UpdateFailed) as excinfo:
        await coordinator._async_update_data()

    assert calls["n"] == 0
    assert "cooldown until" in str(excinfo.value)
    assert coordinator.update_interval.total_seconds() == 300


@pytest.mark.asyncio
async def test_coordinator_clears_cooldown_after_success(monkeypatch) -> None:
    """A successful fetch restores the configured poll interval."""
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

    entry = SimpleNamespace(entry_id="entry", options={}, data={CONF_POLL_INTERVAL: 60})
    coordinator = CodexRatesCoordinator(SimpleNamespace(data={}), entry)
    coordinator._provider = _Provider()
    # Equal to now → cooldown no longer blocks; fetch proceeds and clears state.
    coordinator.rate_limit_cooldown_until = now
    coordinator.update_interval = timedelta(seconds=120)

    result = await coordinator._async_update_data()

    assert result is snapshot
    assert coordinator.rate_limit_cooldown_until is None
    assert coordinator.update_interval == timedelta(seconds=60)


@pytest.mark.asyncio
async def test_diagnostics_expose_active_rate_limit_cooldown(monkeypatch) -> None:
    """Diagnostics should flag an active HTTP 429 cooldown for support."""
    import custom_components.codex_rates.diagnostics as diagnostics_mod

    now = datetime(2026, 9, 16, 12, 30, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(diagnostics_mod, "datetime", _FixedDateTime, raising=False)

    coordinator = SimpleNamespace(
        data=None,
        last_update_success=False,
        poll_interval_seconds=60,
        last_successful_poll_at=datetime(2026, 9, 16, 12, 20, tzinfo=timezone.utc),
        rate_limit_cooldown_until=datetime(2026, 9, 16, 12, 35, tzinfo=timezone.utc),
        last_rate_limit_at=datetime(2026, 9, 16, 12, 28, tzinfo=timezone.utc),
        last_rate_limit_retry_after=420.0,
    )
    entry = SimpleNamespace(
        entry_id="entry",
        title="Codex-LB",
        data={},
        options={},
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry": coordinator}})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["coordinator"]["rate_limit_active"] is True
    assert (
        result["coordinator"]["rate_limit_cooldown_until"]
        == "2026-09-16T12:35:00+00:00"
    )
    assert result["coordinator"]["last_rate_limit_retry_after"] == 420.0


@pytest.mark.asyncio
async def test_coordinator_fills_chatgpt_last_refresh_from_poll(monkeypatch) -> None:
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

    entry = SimpleNamespace(
        entry_id="entry",
        options={},
        data={CONF_POLL_INTERVAL: 60, CONF_MODE: MODE_CHATGPT},
    )
    coordinator = CodexRatesCoordinator(SimpleNamespace(data={}), entry)
    coordinator._provider = _Provider()

    await coordinator._async_update_data()
    assert snapshot.accounts[0].last_refresh_at == now
