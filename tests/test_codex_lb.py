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
        cookie = request.cookies.get("codex_lb_dashboard_session") or request.headers.get(
            "Cookie", ""
        )
        if "cookie-value" not in cookie and request.cookies.get(
            "codex_lb_dashboard_session"
        ) != "cookie-value":
            # Accept explicit Cookie header from provider
            if "cookie-value" not in request.headers.get("Cookie", ""):
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
                        },
                        "resetAtPrimary": "2026-03-04T00:00:00Z",
                        "resetAtSecondary": "2026-03-10T00:00:00Z",
                        "windowMinutesPrimary": 300,
                        "windowMinutesSecondary": 10080,
                        "remainingCreditsPrimary": 425.0,
                        "lastRefreshAt": "2026-03-03T18:30:00Z",
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

    account = snapshot.accounts[0]
    assert account.account_id == "acc_camel"
    assert account.email == "camel@example.com"
    assert account.display_name == "Camel"
    assert account.plan_type == "plus"
    assert account.remaining_5h == 42.5
    assert account.remaining_weekly == 88.0
    assert account.credits_balance == "425.0"
    assert snapshot.pool is not None
    assert snapshot.pool.remaining_5h.mean == 42.5
