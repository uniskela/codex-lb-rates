"""Tests for Codex-LB provider."""

from __future__ import annotations

import aiohttp
import pytest
from aiohttp import web

from custom_components.codex_rates.providers.codex_lb import CodexLbProvider


@pytest.mark.asyncio
async def test_codex_lb_maps_accounts_and_pool(aiohttp_client) -> None:
    async def accounts(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "accounts": [
                    {
                        "account_id": "acc_1",
                        "email": "a@example.com",
                        "display_name": "A",
                        "plan_type": "pro",
                        "status": "active",
                        "usage": {
                            "primary_remaining_percent": 75.5,
                            "secondary_remaining_percent": 90.0,
                        },
                        "reset_at_primary": "2026-03-04T00:00:00Z",
                        "reset_at_secondary": "2026-03-10T00:00:00Z",
                        "window_minutes_primary": 300,
                        "window_minutes_secondary": 10080,
                    },
                    {
                        "account_id": "acc_2",
                        "email": "b@example.com",
                        "status": "active",
                        "usage": {
                            "primary_remaining_percent": 25.5,
                            "secondary_remaining_percent": 50.0,
                        },
                    },
                ]
            }
        )

    async def session_state(request: web.Request) -> web.Response:
        return web.json_response({"authenticated": True, "password_required": False})

    app = web.Application()
    app.router.add_get("/api/accounts", accounts)
    app.router.add_get("/api/dashboard-auth/session", session_state)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        base = str(client.make_url("/")).rstrip("/")
        provider = CodexLbProvider(session, base_url=base)
        snapshot = await provider.async_validate()

    assert len(snapshot.accounts) == 2
    assert snapshot.accounts[0].remaining_5h == 75.5
    assert snapshot.pool is not None
    assert snapshot.pool.remaining_5h.mean == 50.5
    assert snapshot.pool.active_count == 2


@pytest.mark.asyncio
async def test_codex_lb_login_with_password(aiohttp_client) -> None:
    state = {"authed": False}

    async def session_get(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "authenticated": state["authed"],
                "password_required": True,
                "totp_required_on_login": False,
            }
        )

    async def login(request: web.Request) -> web.Response:
        body = await request.json()
        assert body["password"] == "secret"
        state["authed"] = True
        resp = web.json_response(
            {"authenticated": True, "totp_required_on_login": False}
        )
        resp.set_cookie("codex_lb_dashboard_session", "cookie-value")
        return resp

    async def accounts(request: web.Request) -> web.Response:
        if not state["authed"]:
            return web.json_response({"error": "auth"}, status=401)
        cookie = request.cookies.get(
            "codex_lb_dashboard_session"
        ) or request.headers.get("Cookie", "")
        if (
            "cookie-value" not in cookie
            and request.cookies.get("codex_lb_dashboard_session") != "cookie-value"
            and "cookie-value" not in request.headers.get("Cookie", "")
        ):
            return web.json_response({"error": "auth"}, status=401)
        return web.json_response(
            {
                "accounts": [
                    {
                        "account_id": "acc",
                        "status": "active",
                        "usage": {
                            "primary_remaining_percent": 100,
                            "secondary_remaining_percent": 100,
                        },
                    }
                ]
            }
        )

    app = web.Application()
    app.router.add_get("/api/dashboard-auth/session", session_get)
    app.router.add_post("/api/dashboard-auth/password/login", login)
    app.router.add_get("/api/accounts", accounts)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        provider = CodexLbProvider(
            session, base_url=str(client.make_url("/")).rstrip("/"), password="secret"
        )
        snapshot = await provider.async_validate()

    assert len(snapshot.accounts) == 1
    assert snapshot.accounts[0].remaining_5h == 100


@pytest.mark.asyncio
async def test_codex_lb_maps_camel_case_accounts(aiohttp_client) -> None:
    """Live Codex-LB JSON uses DashboardModel camelCase aliases."""

    async def accounts(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "accounts": [
                    {
                        "accountId": "acc_camel",
                        "email": "camel@example.com",
                        "displayName": "Camel",
                        "planType": "plus",
                        "status": "active",
                        "usage": {
                            "primaryRemainingPercent": 42.5,
                            "secondaryRemainingPercent": 88.0,
                            "monthlyRemainingPercent": 55.0,
                        },
                        "resetAtPrimary": "2026-03-04T00:00:00Z",
                        "resetAtSecondary": "2026-03-10T00:00:00Z",
                        "resetAtMonthly": "2026-04-01T00:00:00Z",
                        "windowMinutesPrimary": 300,
                        "windowMinutesSecondary": 10080,
                        "windowMinutesMonthly": 43200,
                        "remainingCreditsPrimary": 425.0,
                        "availableResetCredits": 2,
                        "resetCreditNearestExpiresAt": "2026-03-20T12:00:00Z",
                        "lastRefreshAt": "2026-03-03T18:30:00Z",
                    },
                    {
                        "accountId": "skip_me",
                        "email": "other@example.com",
                        "displayName": "Other",
                        "planType": "pro",
                        "provider": "anthropic",
                        "status": "active",
                        "usage": {"primaryRemainingPercent": 99.0},
                    },
                ]
            }
        )

    async def session_state(request: web.Request) -> web.Response:
        return web.json_response({"authenticated": True, "passwordRequired": False})

    app = web.Application()
    app.router.add_get("/api/accounts", accounts)
    app.router.add_get("/api/dashboard-auth/session", session_state)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        base = str(client.make_url("/")).rstrip("/")
        provider = CodexLbProvider(session, base_url=base)
        snapshot = await provider.async_validate()

    assert len(snapshot.accounts) == 1
    account = snapshot.accounts[0]
    assert account.account_id == "acc_camel"
    assert account.email == "camel@example.com"
    assert account.display_name == "Camel"
    assert account.plan_type == "plus"
    assert account.remaining_5h == 42.5
    assert account.remaining_weekly == 88.0
    assert account.remaining_monthly == 55.0
    assert account.reset_credits == 2
    assert account.reset_credits_expire_at is not None
    assert account.credits_balance == "425.0"
    assert snapshot.pool is not None
    assert snapshot.pool.remaining_5h.mean == 42.5
    assert snapshot.pool.remaining_monthly.mean == 55.0


@pytest.mark.asyncio
async def test_codex_lb_maps_spark_quota_and_omits_absent_accounts(
    aiohttp_client,
) -> None:
    async def accounts(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "accounts": [
                    {
                        "accountId": "pro",
                        "status": "quota_exceeded",
                        "capacityCreditsPrimary": 1500,
                        "additionalQuotas": [
                            {
                                "quotaKey": "codex_spark",
                                "primaryWindow": {
                                    "usedPercent": 0,
                                    "resetAt": 1789494235,
                                    "windowMinutes": 300,
                                },
                                "secondaryWindow": {
                                    "usedPercent": 100,
                                    "resetAt": 1789807641,
                                    "windowMinutes": 10080,
                                },
                            }
                        ],
                    },
                    {
                        "accountId": "team",
                        "status": "quota_exceeded",
                        "capacityCreditsPrimary": 225,
                    },
                ]
            }
        )

    app = web.Application()
    app.router.add_get("/api/accounts", accounts)
    client = await aiohttp_client(app)
    async with aiohttp.ClientSession() as session:
        snapshot = await CodexLbProvider(
            session, base_url=str(client.make_url("/")).rstrip("/")
        )._fetch_accounts()

    assert snapshot.accounts[0].remaining_spark_5h == 100
    assert snapshot.accounts[0].remaining_spark_weekly == 0
    assert snapshot.accounts[1].remaining_spark_5h is None
    assert snapshot.pool is not None
    assert snapshot.pool.remaining_spark_5h.mean == 100
    assert snapshot.pool.remaining_spark_5h.sample_count == 1


@pytest.mark.asyncio
async def test_codex_lb_maps_request_usage_and_non_spark_additional_quotas(
    aiohttp_client,
) -> None:
    async def accounts(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "accounts": [
                    {
                        "accountId": "pro",
                        "status": "active",
                        "usage": {"primaryRemainingPercent": 80},
                        "requestUsage": {
                            "requestCount": 7,
                            "totalTokens": 51480,
                            "cachedInputTokens": 41470,
                            "totalCostUsd": 0.13,
                        },
                        "additionalQuotas": [
                            {
                                "quotaKey": "codex_spark",
                                "limitName": "codex_spark",
                                "meteredFeature": "codex_bengalfox",
                                "displayLabel": "GPT-5.3-Codex-Spark",
                                "routingPolicy": "inherit",
                                "primaryWindow": {
                                    "usedPercent": 0,
                                    "resetAt": 1789494235,
                                    "windowMinutes": 300,
                                },
                                "secondaryWindow": {
                                    "usedPercent": 100,
                                    "resetAt": 1789807641,
                                    "windowMinutes": 10080,
                                },
                            },
                            {
                                "quotaKey": "codex_research",
                                "limitName": "codex_research",
                                "meteredFeature": "codex_research",
                                "displayLabel": "Research",
                                "routingPolicy": "burn_first",
                                "primaryWindow": {
                                    "usedPercent": 40,
                                    "resetAt": 1789494235,
                                    "windowMinutes": 300,
                                },
                            },
                        ],
                    }
                ]
            }
        )

    app = web.Application()
    app.router.add_get("/api/accounts", accounts)
    client = await aiohttp_client(app)
    async with aiohttp.ClientSession() as session:
        snapshot = await CodexLbProvider(
            session, base_url=str(client.make_url("/")).rstrip("/")
        )._fetch_accounts()

    account = snapshot.accounts[0]
    assert account.request_count == 7
    assert account.total_tokens == 51480
    assert account.cached_input_tokens == 41470
    assert account.total_cost_usd == 0.13
    assert account.remaining_spark_5h == 100
    assert account.remaining_spark_weekly == 0
    assert len(account.additional_quotas) == 2
    spark, research = account.additional_quotas
    assert spark.is_spark is True
    assert research.is_spark is False
    assert research.quota_key == "codex_research"
    assert research.routing_policy == "burn_first"
    assert research.primary is not None
    assert research.primary.used_percent == 40
    assert research.primary.remaining_percent == 60
    assert research.as_dict()["primary"]["used_percent"] == 40


@pytest.mark.asyncio
async def test_codex_lb_prefers_canonical_spark_and_keeps_reset_only_windows(
    aiohttp_client,
) -> None:
    async def accounts(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "accounts": [
                    {
                        "accountId": "pro",
                        "status": "active",
                        "additionalQuotas": [
                            {
                                "quotaKey": "codex_other",
                                "limitName": "codex_other",
                                "primaryWindow": {
                                    "usedPercent": 90,
                                    "windowMinutes": 300,
                                },
                            },
                            {
                                "quotaKey": "codex_spark",
                                "meteredFeature": "codex_bengalfox",
                                "primaryWindow": {
                                    "usedPercent": 10,
                                    "windowMinutes": 300,
                                },
                                "secondaryWindow": {
                                    "resetAt": 1789807641,
                                    "windowMinutes": 10080,
                                },
                            },
                        ],
                    }
                ]
            }
        )

    app = web.Application()
    app.router.add_get("/api/accounts", accounts)
    client = await aiohttp_client(app)
    async with aiohttp.ClientSession() as session:
        snapshot = await CodexLbProvider(
            session, base_url=str(client.make_url("/")).rstrip("/")
        )._fetch_accounts()

    account = snapshot.accounts[0]
    assert account.remaining_spark_5h == 90
    assert account.used_spark_5h == 10
    assert account.reset_spark_weekly is not None
    assert account.window_minutes_spark_weekly == 10080
    assert account.remaining_spark_weekly is None
    assert len(account.additional_quotas) == 2
    assert account.additional_quotas[1].secondary is not None
    assert account.additional_quotas[1].secondary.reset_at is not None


@pytest.mark.asyncio
async def test_codex_lb_guest_login(aiohttp_client) -> None:
    state = {"authed": False}

    async def session_get(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "authenticated": state["authed"],
                "guestAccessEnabled": True,
                "guestPasswordRequired": True,
            }
        )

    async def guest_login(request: web.Request) -> web.Response:
        body = await request.json()
        assert body["password"] == "guest-pass"
        state["authed"] = True
        resp = web.json_response({"authenticated": True, "role": "guest"})
        resp.set_cookie("codex_lb_dashboard_session", "guest-cookie")
        return resp

    async def accounts(request: web.Request) -> web.Response:
        if "guest-cookie" not in request.headers.get("Cookie", ""):
            return web.json_response({"error": "auth"}, status=401)
        return web.json_response(
            {
                "accounts": [
                    {
                        "accountId": "g1",
                        "status": "active",
                        "usage": {"primaryRemainingPercent": 33},
                    }
                ]
            }
        )

    app = web.Application()
    app.router.add_get("/api/dashboard-auth/session", session_get)
    app.router.add_post("/api/dashboard-auth/guest/login", guest_login)
    app.router.add_get("/api/accounts", accounts)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        provider = CodexLbProvider(
            session,
            base_url=str(client.make_url("/")).rstrip("/"),
            password="guest-pass",
            login_mode="guest",
        )
        snapshot = await provider.async_validate()

    assert snapshot.accounts[0].remaining_5h == 33.0


@pytest.mark.asyncio
async def test_codex_lb_prefers_account_id_over_generic_id(aiohttp_client) -> None:
    async def accounts(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "accounts": [
                    {
                        "id": "internal-uuid",
                        "accountId": "acc_stable",
                        "email": "stable@example.com",
                        "status": "active",
                        "usage": {"primaryRemainingPercent": 10.0},
                    }
                ]
            }
        )

    async def session_state(request: web.Request) -> web.Response:
        return web.json_response({"authenticated": True, "passwordRequired": False})

    app = web.Application()
    app.router.add_get("/api/accounts", accounts)
    app.router.add_get("/api/dashboard-auth/session", session_state)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        base = str(client.make_url("/")).rstrip("/")
        provider = CodexLbProvider(session, base_url=base)
        snapshot = await provider.async_validate()

    assert len(snapshot.accounts) == 1
    assert snapshot.accounts[0].account_id == "acc_stable"


@pytest.mark.asyncio
async def test_codex_lb_raises_rate_limit_with_retry_after(aiohttp_client) -> None:
    from custom_components.codex_rates.exceptions import CodexRatesRateLimitError

    async def accounts(request: web.Request) -> web.Response:
        return web.json_response(
            {"error": "too many requests"},
            status=429,
            headers={"Retry-After": "120"},
        )

    async def session_state(request: web.Request) -> web.Response:
        return web.json_response({"authenticated": True, "password_required": False})

    app = web.Application()
    app.router.add_get("/api/accounts", accounts)
    app.router.add_get("/api/dashboard-auth/session", session_state)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        provider = CodexLbProvider(
            session, base_url=str(client.make_url("/")).rstrip("/")
        )
        with pytest.raises(CodexRatesRateLimitError) as excinfo:
            await provider.async_fetch()

    assert excinfo.value.retry_after == 120.0
    assert "429" in str(excinfo.value)
