"""Tests for ChatGPT provider and auth.json loading."""

from __future__ import annotations

import json
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web

from custom_components.codex_rates.providers.chatgpt import ChatGptProvider, load_auth_json


@pytest.mark.asyncio
async def test_chatgpt_usage_mapping(aiohttp_client) -> None:
    async def usage(request: web.Request) -> web.Response:
        assert request.headers.get("Authorization") == "Bearer tok"
        assert request.headers.get("ChatGPT-Account-Id") == "acc-9"
        return web.json_response(
            {
                "plan_type": "plus",
                "rate_limit": {
                    "allowed": True,
                    "limit_reached": False,
                    "primary_window": {
                        "used_percent": 20,
                        "limit_window_seconds": 18000,
                        "reset_at": 1704081600,
                    },
                    "secondary_window": {
                        "used_percent": 50,
                        "limit_window_seconds": 604800,
                        "reset_at": 1704499200,
                    },
                },
                "credits": {"balance": "15.0"},
                "rate_limit_reset_credits": {
                    "available_count": 1,
                    "applicable_available_count": 1,
                },
            }
        )

    app = web.Application()
    app.router.add_get("/usage", usage)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        provider = ChatGptProvider(
            session,
            access_token="tok",
            account_id="acc-9",
            usage_url=str(client.make_url("/usage")),
        )
        snapshot = await provider.async_validate()

    account = snapshot.accounts[0]
    assert account.remaining_5h == 80.0
    assert account.remaining_weekly == 50.0
    assert account.plan_type == "plus"
    assert account.credits_balance == "15.0"
    assert account.reset_credits == 1
    assert account.status == "active"
    assert account.window_minutes_5h == 300
    assert account.last_refresh_at is None
    assert account.request_count is None


@pytest.mark.asyncio
async def test_chatgpt_maps_last_refresh_and_request_usage(aiohttp_client) -> None:
    async def usage(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "plan_type": "plus",
                "last_refresh_at": "2026-09-16T12:00:00Z",
                "rate_limit": {
                    "allowed": True,
                    "primary_window": {
                        "used_percent": 10,
                        "limit_window_seconds": 18000,
                    },
                },
                "requestUsage": {
                    "requestCount": 3,
                    "totalTokens": 1200,
                    "cachedInputTokens": 400,
                    "totalCostUsd": 0.02,
                },
            }
        )

    app = web.Application()
    app.router.add_get("/usage", usage)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        provider = ChatGptProvider(
            session,
            access_token="tok",
            account_id="acc-9",
            usage_url=str(client.make_url("/usage")),
        )
        snapshot = await provider.async_validate()

    account = snapshot.accounts[0]
    assert account.last_refresh_at is not None
    assert account.last_refresh_at.isoformat() == "2026-09-16T12:00:00+00:00"
    assert account.request_count == 3
    assert account.total_tokens == 1200
    assert account.cached_input_tokens == 400
    assert account.total_cost_usd == 0.02


@pytest.mark.asyncio
async def test_chatgpt_reset_credits_zero_is_preserved(aiohttp_client) -> None:
    async def usage(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "plan_type": "plus",
                "rate_limit": {
                    "allowed": True,
                    "primary_window": {"used_percent": 0, "limit_window_seconds": 18000},
                },
                "rate_limit_reset_credits": {
                    "available_count": 0,
                    "applicable_available_count": 2,
                },
            }
        )

    app = web.Application()
    app.router.add_get("/usage", usage)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        provider = ChatGptProvider(
            session,
            access_token="tok",
            account_id="acc-9",
            usage_url=str(client.make_url("/usage")),
        )
        snapshot = await provider.async_validate()

    assert snapshot.accounts[0].reset_credits == 0


@pytest.mark.asyncio
async def test_chatgpt_raises_rate_limit_with_retry_after(aiohttp_client) -> None:
    from custom_components.codex_rates.exceptions import CodexRatesRateLimitError

    async def usage(request: web.Request) -> web.Response:
        return web.json_response(
            {"error": "rate limited"},
            status=429,
            headers={"Retry-After": "45"},
        )

    app = web.Application()
    app.router.add_get("/usage", usage)
    client = await aiohttp_client(app)

    async with aiohttp.ClientSession() as session:
        provider = ChatGptProvider(
            session,
            access_token="tok",
            account_id="acc-9",
            usage_url=str(client.make_url("/usage")),
        )
        with pytest.raises(CodexRatesRateLimitError) as excinfo:
            await provider.async_fetch()

    assert excinfo.value.retry_after == 45.0
    assert "429" in str(excinfo.value)


def test_load_auth_json(tmp_path: Path) -> None:
    path = tmp_path / "auth.json"
    path.write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": "a",
                    "refresh_token": "r",
                    "id_token": "i",
                    "account_id": "acc",
                }
            }
        ),
        encoding="utf-8",
    )
    tokens = load_auth_json(str(path))
    assert tokens["access_token"] == "a"
    assert tokens["account_id"] == "acc"
    assert tokens["refresh_token"] == "r"
