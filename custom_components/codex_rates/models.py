"""Normalized quota models for Codex Rates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any

# Codex-LB / ChatGPT additional-quota keys treated as the Spark model window.
_SPARK_QUOTA_KEYS = frozenset({"codex_spark", "codex_other", "gpt-5.3-codex-spark"})
_SPARK_METERED_FEATURES = frozenset({"codex_bengalfox"})


@dataclass(slots=True)
class AdditionalQuotaWindow:
    """One primary/secondary window inside an additional quota row."""

    used_percent: float | None = None
    remaining_percent: float | None = None
    reset_at: datetime | None = None
    window_minutes: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize for Home Assistant attributes."""
        payload: dict[str, Any] = {}
        if self.used_percent is not None:
            payload["used_percent"] = self.used_percent
        if self.remaining_percent is not None:
            payload["remaining_percent"] = self.remaining_percent
        if self.reset_at is not None:
            payload["resets_at"] = self.reset_at.isoformat()
        if self.window_minutes is not None:
            payload["window_minutes"] = self.window_minutes
        return payload


@dataclass(slots=True)
class AdditionalQuota:
    """Normalized Codex-LB ``additionalQuotas`` row (Spark or other)."""

    quota_key: str | None = None
    limit_name: str | None = None
    metered_feature: str | None = None
    display_label: str | None = None
    routing_policy: str | None = None
    primary: AdditionalQuotaWindow | None = None
    secondary: AdditionalQuotaWindow | None = None

    @property
    def is_spark(self) -> bool:
        """True when this row is the known Codex Spark gated quota."""
        key = (self.quota_key or "").strip().lower()
        feature = (self.metered_feature or "").strip().lower()
        limit = (self.limit_name or "").strip().lower()
        return (
            key in _SPARK_QUOTA_KEYS
            or limit in _SPARK_QUOTA_KEYS
            or feature in _SPARK_METERED_FEATURES
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize for Home Assistant attributes."""
        payload: dict[str, Any] = {}
        if self.quota_key is not None:
            payload["quota_key"] = self.quota_key
        if self.limit_name is not None:
            payload["limit_name"] = self.limit_name
        if self.metered_feature is not None:
            payload["metered_feature"] = self.metered_feature
        if self.display_label is not None:
            payload["display_label"] = self.display_label
        if self.routing_policy is not None:
            payload["routing_policy"] = self.routing_policy
        if self.primary is not None:
            payload["primary"] = self.primary.as_dict()
        if self.secondary is not None:
            payload["secondary"] = self.secondary.as_dict()
        return payload


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
    capacity_5h: float | None = None
    capacity_weekly: float | None = None
    capacity_monthly: float | None = None
    remaining_spark_5h: float | None = None
    remaining_spark_weekly: float | None = None
    used_spark_5h: float | None = None
    used_spark_weekly: float | None = None
    reset_spark_5h: datetime | None = None
    reset_spark_weekly: datetime | None = None
    window_minutes_spark_5h: int | None = None
    window_minutes_spark_weekly: int | None = None
    request_count: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    total_cost_usd: float | None = None
    additional_quotas: list[AdditionalQuota] = field(default_factory=list)
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
    # Shared window length in minutes; None if unknown or mixed.
    window_minutes: int | None = None
    # Mean remaining % keyed by window length when more than one duration is present.
    by_minutes: dict[int, float] = field(default_factory=dict)
    weighted_capacity: float | None = None
    weighting_method: str = "equal"
    missing_weight_count: int = 0


@dataclass(slots=True)
class PoolAggregate:
    """Pool-level aggregates for Codex-LB."""

    remaining_5h: WindowAggregate
    remaining_weekly: WindowAggregate
    remaining_monthly: WindowAggregate
    remaining_spark_5h: WindowAggregate
    remaining_spark_weekly: WindowAggregate
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
    capacities: list[float | None] | None = None,
) -> WindowAggregate:
    if not values:
        return WindowAggregate(mean=None, min=None, max=None, sample_count=0)

    valid_capacities = capacities if capacities is not None else [None] * len(values)
    missing_weight_count = sum(
        capacity is None or not isfinite(capacity) or capacity <= 0
        for capacity in valid_capacities
    )
    if len(valid_capacities) != len(values) or missing_weight_count:
        weights = [1.0] * len(values)
        weighting_method = "equal_missing_capacity"
    else:
        weights = [float(capacity) for capacity in valid_capacities]
        weighting_method = "capacity_credits"
    by_minutes: dict[int, list[int]] = {}
    if minutes is not None:
        for index, mins in enumerate(minutes):
            if mins is not None:
                by_minutes.setdefault(mins, []).append(index)

    def mean(indices: list[int]) -> float:
        return round(
            sum(values[i] * weights[i] for i in indices)
            / sum(weights[i] for i in indices),
            2,
        )

    duration_means = {mins: mean(indices) for mins, indices in by_minutes.items()}

    # Keep every measured window in the pool.  A duration disagreement is useful
    # context, not a reason to silently omit quota from another account type.
    modal_minutes: int | None = None
    if by_minutes:
        modal_minutes = max(by_minutes.items(), key=lambda item: len(item[1]))[0]
        if len(by_minutes) > 1:
            modal_minutes = None

    return WindowAggregate(
        mean=mean(list(range(len(values)))),
        min=round(min(values), 2),
        max=round(max(values), 2),
        sample_count=len(values),
        window_minutes=modal_minutes,
        by_minutes=duration_means if len(duration_means) > 1 else {},
        weighted_capacity=round(sum(weights), 2)
        if weighting_method == "capacity_credits"
        else None,
        weighting_method=weighting_method,
        missing_weight_count=missing_weight_count,
    )


def compute_pool_aggregate(accounts: list[AccountQuota]) -> PoolAggregate:
    """Capacity-weighted remaining % across every account with a measured window."""
    active = [a for a in accounts if (a.status or "").lower() == "active"]

    def _pairs(
        getter_remaining: Any,
        getter_minutes: Any,
        getter_capacity: Any,
    ) -> tuple[list[float], list[int | None], list[float | None]]:
        vals: list[float] = []
        mins: list[int | None] = []
        capacities: list[float | None] = []
        for account in accounts:
            remaining = getter_remaining(account)
            if remaining is None or not isfinite(remaining):
                continue
            vals.append(remaining)
            mins.append(getter_minutes(account))
            capacities.append(getter_capacity(account))
        return vals, mins, capacities

    five, five_m, five_c = _pairs(
        lambda a: a.remaining_5h, lambda a: a.window_minutes_5h, lambda a: a.capacity_5h
    )
    weekly, weekly_m, weekly_c = _pairs(
        lambda a: a.remaining_weekly,
        lambda a: a.window_minutes_weekly,
        lambda a: a.capacity_weekly,
    )
    monthly, monthly_m, monthly_c = _pairs(
        lambda a: a.remaining_monthly,
        lambda a: a.window_minutes_monthly,
        lambda a: a.capacity_monthly,
    )
    spark_five, spark_five_m, spark_five_c = _pairs(
        lambda a: a.remaining_spark_5h,
        lambda a: a.window_minutes_spark_5h,
        lambda a: a.capacity_5h,
    )
    spark_weekly, spark_weekly_m, spark_weekly_c = _pairs(
        lambda a: a.remaining_spark_weekly,
        lambda a: a.window_minutes_spark_weekly,
        lambda a: a.capacity_weekly,
    )
    return PoolAggregate(
        remaining_5h=_window_aggregate(five, five_m, five_c),
        remaining_weekly=_window_aggregate(weekly, weekly_m, weekly_c),
        remaining_monthly=_window_aggregate(monthly, monthly_m, monthly_c),
        remaining_spark_5h=_window_aggregate(spark_five, spark_five_m, spark_five_c),
        remaining_spark_weekly=_window_aggregate(
            spark_weekly, spark_weekly_m, spark_weekly_c
        ),
        account_count=len(accounts),
        active_count=len(active),
    )


def remaining_from_used(used_percent: float | None) -> float | None:
    """Convert used percent to remaining percent."""
    if used_percent is None:
        return None
    return round(max(0.0, min(100.0, 100.0 - float(used_percent))), 2)


def parse_iso_datetime(value: str | float | None) -> datetime | None:
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
