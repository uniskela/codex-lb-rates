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


def test_pool_aggregate_includes_exhausted_accounts_and_skips_unknown() -> None:
    accounts = [
        AccountQuota(
            account_id="a", status="active", remaining_5h=80, remaining_weekly=90
        ),
        AccountQuota(
            account_id="b", status="active", remaining_5h=60, remaining_weekly=None
        ),
        AccountQuota(
            account_id="c", status="paused", remaining_5h=10, remaining_weekly=10
        ),
        AccountQuota(
            account_id="d", status="active", remaining_5h=None, remaining_weekly=70
        ),
    ]
    pool = compute_pool_aggregate(accounts)
    assert pool.account_count == 4
    assert pool.active_count == 3
    assert pool.remaining_5h.mean == 50.0
    assert pool.remaining_5h.min == 10.0
    assert pool.remaining_5h.max == 80.0
    assert pool.remaining_5h.sample_count == 3
    assert pool.remaining_weekly.mean == 56.67
    assert pool.remaining_weekly.sample_count == 3
    assert pool.remaining_monthly.mean is None


def test_pool_aggregate_keeps_mixed_window_durations_visible() -> None:
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
    assert pool.remaining_5h.window_minutes is None
    assert pool.remaining_5h.mean == 50.0
    assert pool.remaining_5h.by_minutes == {300: 70.0, 10080: 10.0}
    assert pool.remaining_monthly.mean == 45.0
    assert pool.remaining_monthly.window_minutes == 43200


def test_pool_aggregate_weights_by_server_capacity_and_preserves_zero() -> None:
    pool = compute_pool_aggregate(
        [
            AccountQuota(account_id="pro", remaining_5h=0, capacity_5h=1500),
            AccountQuota(account_id="team", remaining_5h=100, capacity_5h=225),
            AccountQuota(account_id="unknown", remaining_5h=None, capacity_5h=1500),
        ]
    )
    assert pool.remaining_5h.mean == 13.04
    assert pool.remaining_5h.sample_count == 2
    assert pool.remaining_5h.weighted_capacity == 1725


def test_weekly_pool_includes_three_exhausted_accounts_and_spark() -> None:
    accounts = [
        AccountQuota(
            account_id=str(i),
            status="quota_exceeded",
            remaining_weekly=0,
            capacity_weekly=50400,
            remaining_spark_weekly=0,
        )
        for i in range(2)
    ] + [
        AccountQuota(
            account_id="team",
            status="quota_exceeded",
            remaining_weekly=0,
            capacity_weekly=7560,
        ),
        AccountQuota(
            account_id="available",
            status="active",
            remaining_weekly=79,
            capacity_weekly=50400,
            remaining_spark_weekly=0,
        ),
    ]
    pool = compute_pool_aggregate(accounts)
    assert pool.remaining_weekly.mean == 25.08
    assert pool.remaining_weekly.sample_count == 4
    assert pool.remaining_weekly.min == 0
    assert pool.remaining_spark_weekly.mean == 0
    assert pool.remaining_spark_weekly.sample_count == 3
    assert pool.remaining_spark_5h.mean is None


def test_missing_capacity_never_mixes_credits_with_unit_weights() -> None:
    for missing in (None, 0, float("nan"), float("inf")):
        pool = compute_pool_aggregate(
            [
                AccountQuota(
                    account_id="large", remaining_weekly=0, capacity_weekly=50400
                ),
                AccountQuota(
                    account_id="unknown", remaining_weekly=100, capacity_weekly=missing
                ),
            ]
        )
        assert pool.remaining_weekly.mean == 50
        assert pool.remaining_weekly.sample_count == 2
        assert pool.remaining_weekly.missing_weight_count == 1
        assert pool.remaining_weekly.weighting_method == "equal_missing_capacity"
        assert pool.remaining_weekly.weighted_capacity is None


def test_mixed_durations_have_capacity_weighted_subgroups() -> None:
    pool = compute_pool_aggregate(
        [
            AccountQuota(
                account_id="a",
                remaining_weekly=0,
                capacity_weekly=100,
                window_minutes_weekly=10080,
            ),
            AccountQuota(
                account_id="b",
                remaining_weekly=100,
                capacity_weekly=300,
                window_minutes_weekly=10080,
            ),
            AccountQuota(
                account_id="c",
                remaining_weekly=20,
                capacity_weekly=100,
                window_minutes_weekly=43200,
            ),
        ]
    )
    assert pool.remaining_weekly.mean == 64
    assert pool.remaining_weekly.window_minutes is None
    assert pool.remaining_weekly.by_minutes == {10080: 75, 43200: 20}
