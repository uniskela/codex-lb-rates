"""Exceptions for Codex Rates."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import isfinite


class CodexRatesError(Exception):
    """Base error."""


class CodexRatesAuthError(CodexRatesError):
    """Authentication failed permanently until user reconfigures."""


class CodexRatesApiError(CodexRatesError):
    """Upstream API returned an unexpected error."""


class CodexRatesRateLimitError(CodexRatesApiError):
    """Upstream returned HTTP 429 (temporary). Optional Retry-After in seconds.

    Distinct from account quota status ``rate_limited``, which is a normalized
    usage/status string from the provider payload — not an HTTP cooldown.
    """

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header (delta-seconds or HTTP-date) into seconds."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        seconds = None
    if seconds is not None and isfinite(seconds) and seconds >= 0:
        return seconds
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = (when.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, delta)
