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

    entry = SimpleNamespace(options={}, data={CONF_POLL_INTERVAL: 60})
    coordinator = CodexRatesCoordinator(SimpleNamespace(), entry)

    assert coordinator._cooldown_seconds(None) == DEFAULT_RATE_LIMIT_COOLDOWN
    assert coordinator._cooldown_seconds(5) == MIN_POLL_INTERVAL
    assert coordinator._cooldown_seconds(99999) == MAX_RATE_LIMIT_COOLDOWN
