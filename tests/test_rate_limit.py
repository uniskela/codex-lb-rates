"""Tests for Retry-After parsing and rate-limit exception typing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.codex_rates.exceptions import (
    CodexRatesApiError,
    CodexRatesRateLimitError,
    parse_retry_after,
)


def test_rate_limit_error_is_api_error_subclass() -> None:
    err = CodexRatesRateLimitError("boom", retry_after=30)
    assert isinstance(err, CodexRatesApiError)
    assert err.retry_after == 30


def test_parse_retry_after_delta_seconds() -> None:
    assert parse_retry_after("90") == 90.0
    assert parse_retry_after(" 15.5 ") == 15.5
    assert parse_retry_after("") is None
    assert parse_retry_after(None) is None
    assert parse_retry_after("not-a-date") is None


def test_parse_retry_after_http_date() -> None:
    when = datetime.now(timezone.utc) + timedelta(seconds=75)
    # RFC 1123
    header = when.strftime("%a, %d %b %Y %H:%M:%S GMT")
    seconds = parse_retry_after(header)
    assert seconds is not None
    assert 60 <= seconds <= 90


def test_coordinator_cooldown_defaults_and_caps() -> None:
    from types import SimpleNamespace

    from custom_components.codex_rates.const import (
        CONF_POLL_INTERVAL,
        DEFAULT_RATE_LIMIT_COOLDOWN,
        MAX_RATE_LIMIT_COOLDOWN,
        MIN_POLL_INTERVAL,
    )
    from custom_components.codex_rates.coordinator import CodexRatesCoordinator

    entry = SimpleNamespace(entry_id="entry", options={}, data={CONF_POLL_INTERVAL: 60})
    coordinator = CodexRatesCoordinator(SimpleNamespace(data={}), entry)

    assert coordinator._cooldown_seconds(None) == DEFAULT_RATE_LIMIT_COOLDOWN
    assert coordinator._cooldown_seconds(5) == MIN_POLL_INTERVAL
    assert coordinator._cooldown_seconds(99999) == MAX_RATE_LIMIT_COOLDOWN
    assert coordinator._cooldown_seconds(60.5) == 61


async def test_cooldown_survives_coordinator_recreation(monkeypatch) -> None:
    """Options reloads and failed first-refresh retries must respect Retry-After."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import pytest
    from homeassistant.helpers.update_coordinator import UpdateFailed
    import custom_components.codex_rates.coordinator as coordinator_mod
    from custom_components.codex_rates.models import ProviderSnapshot

    now = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(coordinator_mod, "datetime", Clock)
    hass = SimpleNamespace(data={})
    entry = SimpleNamespace(entry_id="entry", options={}, data={})
    first = coordinator_mod.CodexRatesCoordinator(hass, entry)
    first._provider = SimpleNamespace(
        async_fetch=AsyncMock(
            side_effect=CodexRatesRateLimitError("limited", retry_after=120)
        )
    )
    with pytest.raises(UpdateFailed):
        await first._async_update_data()

    entry.options = {"poll_interval": 90}
    reloaded = coordinator_mod.CodexRatesCoordinator(hass, entry)
    fetch = AsyncMock(return_value=ProviderSnapshot(accounts=[]))
    reloaded._provider = SimpleNamespace(async_fetch=fetch)
    with pytest.raises(UpdateFailed, match="cooldown"):
        await reloaded._async_update_data()
    fetch.assert_not_awaited()
    assert reloaded.update_interval == timedelta(seconds=120)

    # A separate config entry must still be able to poll.
    other = coordinator_mod.CodexRatesCoordinator(
        hass, SimpleNamespace(entry_id="other", options={}, data={})
    )
    other._provider = SimpleNamespace(
        async_fetch=AsyncMock(return_value=ProviderSnapshot(accounts=[]))
    )
    await other._async_update_data()

    now += timedelta(seconds=120)
    await reloaded._async_update_data()
    fetch.assert_awaited_once()
    assert reloaded.update_interval == timedelta(seconds=90)
    fresh = coordinator_mod.CodexRatesCoordinator(hass, entry)
    assert fresh.rate_limit_cooldown_until is None


async def test_failed_first_refresh_closes_private_session(monkeypatch) -> None:
    """HA does not call unload when setup fails during its first refresh."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import pytest
    import custom_components.codex_rates as integration

    coordinator = SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(side_effect=RuntimeError("retry")),
        async_shutdown_provider=AsyncMock(),
    )
    monkeypatch.setattr(integration, "CodexRatesCoordinator", lambda *args: coordinator)
    with pytest.raises(RuntimeError, match="retry"):
        await integration.async_setup_entry(SimpleNamespace(data={}), SimpleNamespace())
    coordinator.async_shutdown_provider.assert_awaited_once()
