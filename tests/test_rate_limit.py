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
