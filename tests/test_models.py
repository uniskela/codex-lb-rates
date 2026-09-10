"""Tests for models and pool aggregates."""

from custom_components.codex_rates.models import (
    AccountQuota,
    compute_pool_aggregate,
    remaining_from_used,
)


def test_remaining_from_used() -> None:
    assert remaining_from_used(25) == 75.0
    assert remaining_from_used(0) == 100.0
    assert remaining_from_used(100) == 0.0
    assert remaining_from_used(None) is None


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
