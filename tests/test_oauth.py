"""Tests for OAuth helpers."""

import base64
import json

import pytest

from custom_components.codex_rates.exceptions import CodexRatesAuthError
from custom_components.codex_rates.oauth import (
    account_id_from_id_token,
    build_authorization_url,
    generate_pkce_pair,
    parse_callback_url,
    pkce_challenge,
    start_pkce_session,
)


def test_pkce_pair_deterministic_challenge() -> None:
    verifier, challenge = generate_pkce_pair()
    assert challenge == pkce_challenge(verifier)
    assert len(verifier) > 10


def test_build_authorization_url_contains_client() -> None:
    url = build_authorization_url(state="abc", code_challenge="chal")
    assert "auth.openai.com/oauth/authorize" in url
    assert "client_id=app_EMoamEEZ73f0CkXaXp7hrann" in url
    assert "code_challenge=chal" in url
    assert "state=abc" in url


def test_parse_callback_url() -> None:
    code, state = parse_callback_url(
        "http://localhost:1455/auth/callback?code=thecode&state=thestate"
    )
    assert code == "thecode"
    assert state == "thestate"


def test_parse_callback_url_invalid() -> None:
    with pytest.raises(CodexRatesAuthError):
        parse_callback_url("http://localhost:1455/auth/callback")


def test_start_pkce_session() -> None:
    session = start_pkce_session()
    assert session.state
    assert session.code_verifier
    assert session.state in session.authorization_url


def _fake_jwt(claims: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


def test_account_id_from_id_token() -> None:
    token = _fake_jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acc-1"}})
    assert account_id_from_id_token(token) == "acc-1"
