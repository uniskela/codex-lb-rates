"""Normalized quota models for Codex Rates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class AccountQuota:
    """Quota state for a single Codex / ChatGPT account."""

    account_id: str
    email: str | None = None
    display_name: str | None = None
    status: str = "unknown"
    remaining_5h: float | None = None
    remaining_weekly: float | None = None
    remaining_monthly: float | None = None
    used_5h: float | None = None
    used_weekly: float | None = None
    used_monthly: float | None = None
    reset_5h: datetime | None = None
    reset_weekly: datetime | None = None
    reset_monthly: datetime | None = None
    window_minutes_5h: int | None = None
    window_minutes_weekly: int | None = None
    window_minutes_monthly: int | None = None
    plan_type: str | None = None
    credits_balance: str | None = None
    reset_credits: int | None = None
    reset_credits_expire_at: datetime | None = None
    last_refresh_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Friendly name for device / entity naming."""
        return self.display_name or self.email or self.account_id


@dataclass(slots=True)
class WindowAggregate:
    """Aggregate stats for one quota window across accounts."""

    mean: float | None
    min: float | None
    max: float | None
    sample_count: int
    # Most common window length among samples (minutes); None if unknown/mixed evenly.
    window_minutes: int | None = None
    # Mean remaining % keyed by window length when more than one duration is present.
    by_minutes: dict[int, float] = field(default_factory=dict)


@dataclass(slots=True)
class PoolAggregate:
    """Pool-level aggregates for Codex-LB."""

    remaining_5h: WindowAggregate
    remaining_weekly: WindowAggregate
    remaining_monthly: WindowAggregate
    account_count: int
    active_count: int


@dataclass(slots=True)
class ProviderSnapshot:
    """Result of a provider poll."""

    accounts: list[AccountQuota]
    pool: PoolAggregate | None = None


def _window_aggregate(
    values: list[float],
    minutes: list[int | None] | None = None,
) -> WindowAggregate:
    if not values:
        return WindowAggregate(mean=None, min=None, max=None, sample_count=0)

    by_minutes: dict[int, list[float]] = {}
    if minutes is not None and len(minutes) == len(values):
        for value, mins in zip(values, minutes, strict=True):
            if mins is None:
                continue
            by_minutes.setdefault(mins, []).append(value)

    duration_means = {
        mins: round(sum(group) / len(group), 2) for mins, group in by_minutes.items()
    }

    # Prefer the dominant duration's mean when accounts disagree on window length
    # (e.g. mixed plan windows in the same slot). Fall back to all samples.
    modal_minutes: int | None = None
    mean_values = values
    if by_minutes:
        modal_minutes = max(by_minutes.items(), key=lambda item: len(item[1]))[0]
        if len(by_minutes) > 1:
            mean_values = by_minutes[modal_minutes]

    return WindowAggregate(
        mean=round(sum(mean_values) / len(mean_values), 2),
        min=round(min(values), 2),
        max=round(max(values), 2),
        sample_count=len(values),
        window_minutes=modal_minutes,
        by_minutes=duration_means if len(duration_means) > 1 else {},
    )


def compute_pool_aggregate(accounts: list[AccountQuota]) -> PoolAggregate:
    """Mean/min/max remaining % across active accounts only."""
    active = [a for a in accounts if (a.status or "").lower() == "active"]

    def _pairs(
        getter_remaining: Any, getter_minutes: Any
    ) -> tuple[list[float], list[int | None]]:
        vals: list[float] = []
        mins: list[int | None] = []
        for account in active:
            remaining = getter_remaining(account)
            if remaining is None:
                continue
            vals.append(remaining)
            mins.append(getter_minutes(account))
        return vals, mins

    five, five_m = _pairs(lambda a: a.remaining_5h, lambda a: a.window_minutes_5h)
    weekly, weekly_m = _pairs(
        lambda a: a.remaining_weekly, lambda a: a.window_minutes_weekly
    )
    monthly, monthly_m = _pairs(
        lambda a: a.remaining_monthly, lambda a: a.window_minutes_monthly
    )
    return PoolAggregate(
        remaining_5h=_window_aggregate(five, five_m),
        remaining_weekly=_window_aggregate(weekly, weekly_m),
        remaining_monthly=_window_aggregate(monthly, monthly_m),
        account_count=len(accounts),
        active_count=len(active),
    )


def remaining_from_used(used_percent: float | None) -> float | None:
    """Convert used percent to remaining percent."""
    if used_percent is None:
        return None
    return round(max(0.0, min(100.0, 100.0 - float(used_percent))), 2)


def parse_iso_datetime(value: str | int | float | None) -> datetime | None:
    """Parse ISO-8601 or unix timestamp into timezone-aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return datetime.fromtimestamp(float(text), tz=timezone.utc)
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def format_reset_countdown(
    when: datetime | None, *, now: datetime | None = None
) -> str | None:
    """Format time until reset as ``Xd XXh`` / ``Xh`` (hours granularity)."""
    if when is None:
        return None
    current = now or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    seconds = int((when - current).total_seconds())
    if seconds <= 0:
        return "0h"
    # Ceil to whole hours so short remainders don't show as 0h early.
    hours_total = (seconds + 3599) // 3600
    days, hours = divmod(hours_total, 24)
    if days >= 1:
        return f"{days}d {hours}h"
    return f"{hours}h"
