"""Tests for models and pool aggregates."""

from datetime import datetime, timezone

from custom_components.codex_rates.models import (
    AccountQuota,
    compute_pool_aggregate,
    format_reset_countdown,
    remaining_from_used,
)


def test_remaining_from_used() -> None:
    assert remaining_from_used(25) == 75.0
    assert remaining_from_used(0) == 100.0
    assert remaining_from_used(100) == 0.0
    assert remaining_from_used(None) is None


def test_format_reset_countdown() -> None:
    now = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    assert format_reset_countdown(None, now=now) is None
    assert (
        format_reset_countdown(datetime(2026, 3, 1, 16, 0, tzinfo=timezone.utc), now=now)
        == "4h"
    )
    assert (
        format_reset_countdown(datetime(2026, 3, 5, 2, 0, tzinfo=timezone.utc), now=now)
        == "3d 14h"
    )
    assert (
        format_reset_countdown(datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc), now=now)
        == "0h"
    )
    # Sub-hour remaining ceils to 1h
    assert (
        format_reset_countdown(datetime(2026, 3, 1, 12, 30, tzinfo=timezone.utc), now=now)
        == "1h"
    )


def test_pool_aggregate_active_only_skips_null() -> None:
    accounts = [
        AccountQuota(account_id="a", status="active", remaining_5h=80, remaining_weekly=90),
        AccountQuota(account_id="b", status="active", remaining_5h=60, remaining_weekly=None),
        AccountQuota(account_id="c", status="paused", remaining_5h=10, remaining_weekly=10),
        AccountQuota(account_id="d", status="active", remaining_5h=None, remaining_weekly=70),
    ]
    pool = compute_pool_aggregate(accounts)
    assert pool.account_count == 4
    assert pool.active_count == 3
    assert pool.remaining_5h.mean == 70.0
    assert pool.remaining_5h.min == 60.0
    assert pool.remaining_5h.max == 80.0
    assert pool.remaining_5h.sample_count == 2
    assert pool.remaining_weekly.mean == 80.0
    assert pool.remaining_weekly.sample_count == 2
    assert pool.remaining_monthly.mean is None


def test_pool_aggregate_prefers_dominant_window_minutes() -> None:
    accounts = [
        AccountQuota(
            account_id="a",
            status="active",
            remaining_5h=80,
            window_minutes_5h=300,
            remaining_monthly=40,
            window_minutes_monthly=43200,
        ),
        AccountQuota(
            account_id="b",
            status="active",
            remaining_5h=60,
            window_minutes_5h=300,
            remaining_monthly=50,
            window_minutes_monthly=43200,
        ),
        AccountQuota(
            account_id="c",
            status="active",
            remaining_5h=10,
            window_minutes_5h=10080,  # mismatched duration in the 5h slot
        ),
    ]
    pool = compute_pool_aggregate(accounts)
    assert pool.remaining_5h.window_minutes == 300
    assert pool.remaining_5h.mean == 70.0  # dominant 300-minute group only
    assert pool.remaining_5h.by_minutes == {300: 70.0, 10080: 10.0}
    assert pool.remaining_monthly.mean == 45.0
    assert pool.remaining_monthly.window_minutes == 43200
