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
    used_5h: float | None = None
    used_weekly: float | None = None
    reset_5h: datetime | None = None
    reset_weekly: datetime | None = None
    window_minutes_5h: int | None = None
    window_minutes_weekly: int | None = None
    plan_type: str | None = None
    credits_balance: str | None = None
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


@dataclass(slots=True)
class PoolAggregate:
    """Pool-level aggregates for Codex-LB."""

    remaining_5h: WindowAggregate
    remaining_weekly: WindowAggregate
    account_count: int
    active_count: int


@dataclass(slots=True)
class ProviderSnapshot:
    """Result of a provider poll."""

    accounts: list[AccountQuota]
    pool: PoolAggregate | None = None


def _window_aggregate(values: list[float]) -> WindowAggregate:
    if not values:
        return WindowAggregate(mean=None, min=None, max=None, sample_count=0)
    return WindowAggregate(
        mean=round(sum(values) / len(values), 2),
        min=round(min(values), 2),
        max=round(max(values), 2),
        sample_count=len(values),
    )


def compute_pool_aggregate(accounts: list[AccountQuota]) -> PoolAggregate:
    """Mean/min/max remaining % across active accounts only."""
    active = [a for a in accounts if (a.status or "").lower() == "active"]
    five = [a.remaining_5h for a in active if a.remaining_5h is not None]
    weekly = [a.remaining_weekly for a in active if a.remaining_weekly is not None]
    return PoolAggregate(
        remaining_5h=_window_aggregate(five),
        remaining_weekly=_window_aggregate(weekly),
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
