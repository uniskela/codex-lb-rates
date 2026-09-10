"""OpenAI Codex CLI-compatible OAuth helpers."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, quote

import aiohttp

from .const import (
    OAUTH_AUTH_BASE_URL,
    OAUTH_CLIENT_ID,
    OAUTH_ORIGINATOR,
    OAUTH_REDIRECT_URI,
    OAUTH_SCOPE,
)
from .exceptions import CodexRatesApiError, CodexRatesAuthError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OAuthTokens:
    """Tokens returned by OpenAI OAuth."""

    access_token: str
    refresh_token: str
    id_token: str


@dataclass(frozen=True)
class DeviceCodeChallenge:
    """Device-code challenge details for the user."""

    verification_url: str
    user_code: str
    device_auth_id: str
    interval_seconds: int
    expires_in_seconds: int


@dataclass(frozen=True)
class PkceSession:
    """In-progress PKCE browser flow."""

    state: str
    code_verifier: str
    authorization_url: str


def pkce_challenge(verifier: str) -> str:
    """Create S256 code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """Return (verifier, challenge)."""
    verifier = secrets.token_urlsafe(32)
    return verifier, pkce_challenge(verifier)


def build_authorization_url(*, state: str, code_challenge: str) -> str:
    """Build OpenAI authorize URL for Codex CLI client."""
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": OAUTH_SCOPE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": OAUTH_ORIGINATOR,
    }
    query = urlencode(params, quote_via=quote)
    return f"{OAUTH_AUTH_BASE_URL.rstrip('/')}/oauth/authorize?{query}"


def start_pkce_session() -> PkceSession:
    """Start a PKCE session for paste-callback flow."""
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(16)
    return PkceSession(
        state=state,
        code_verifier=verifier,
        authorization_url=build_authorization_url(state=state, code_challenge=challenge),
    )


def parse_callback_url(callback_url: str) -> tuple[str, str]:
    """Extract (code, state) from a pasted localhost callback URL."""
    parsed = urlparse(callback_url.strip())
    query = parse_qs(parsed.query)
    code = (query.get("code") or [None])[0]
    state = (query.get("state") or [None])[0]
    if not code or not state:
        raise CodexRatesAuthError("Invalid OAuth callback URL: missing code or state")
    return code, state


def account_id_from_id_token(id_token: str) -> str | None:
    """Best-effort extract ChatGPT account id from JWT claims."""
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        data = base64.urlsafe_b64decode(payload + padding)
        import json

        claims = json.loads(data.decode("utf-8"))
        for key in (
            "https://api.openai.com/auth.chatgpt_account_id",
            "chatgpt_account_id",
            "account_id",
            "org_id",
        ):
            value = claims.get(key)
            if isinstance(value, str) and value:
                return value
        auth_claim = claims.get("https://api.openai.com/auth")
        if isinstance(auth_claim, dict):
            value = auth_claim.get("chatgpt_account_id")
            if isinstance(value, str) and value:
                return value
        return claims.get("email") if isinstance(claims.get("email"), str) else None
    except Exception:  # noqa: BLE001 — best-effort claim parse
        return None


def email_from_id_token(id_token: str) -> str | None:
    """Extract email claim from id token when present."""
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        data = base64.urlsafe_b64decode(payload + padding)
        import json

        claims = json.loads(data.decode("utf-8"))
        email = claims.get("email")
        return email if isinstance(email, str) else None
    except Exception:  # noqa: BLE001
        return None


async def exchange_authorization_code(
    session: aiohttp.ClientSession,
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str = OAUTH_REDIRECT_URI,
) -> OAuthTokens:
    """Exchange authorization code for tokens."""
    url = f"{OAUTH_AUTH_BASE_URL.rstrip('/')}/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": OAUTH_CLIENT_ID,
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }
    async with session.post(
        url,
        data=urlencode(payload, quote_via=quote),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        data = await _safe_json(resp)
        if resp.status >= 400:
            raise CodexRatesAuthError(_error_message(data, resp.status))
        return _parse_tokens(data)


async def refresh_access_token(
    session: aiohttp.ClientSession,
    *,
    refresh_token: str,
) -> OAuthTokens:
    """Refresh access token using refresh_token grant."""
    url = f"{OAUTH_AUTH_BASE_URL.rstrip('/')}/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": OAUTH_CLIENT_ID,
        "refresh_token": refresh_token,
    }
    async with session.post(
        url,
        data=urlencode(payload, quote_via=quote),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        data = await _safe_json(resp)
        if resp.status >= 400:
            raise CodexRatesAuthError(_error_message(data, resp.status))
        # Some responses omit rotated refresh/id tokens — keep caller-supplied refresh
        access = data.get("access_token")
        if not isinstance(access, str) or not access:
            raise CodexRatesAuthError("OAuth refresh response missing access_token")
        new_refresh = data.get("refresh_token")
        id_token = data.get("id_token")
        return OAuthTokens(
            access_token=access,
            refresh_token=new_refresh if isinstance(new_refresh, str) and new_refresh else refresh_token,
            id_token=id_token if isinstance(id_token, str) else "",
        )


async def request_device_code(session: aiohttp.ClientSession) -> DeviceCodeChallenge:
    """Start device-code login."""
    url = f"{OAUTH_AUTH_BASE_URL.rstrip('/')}/api/accounts/deviceauth/usercode"
    async with session.post(
        url,
        json={"client_id": OAUTH_CLIENT_ID},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        data = await _safe_json(resp)
        if resp.status == 404:
            raise CodexRatesApiError(
                "Device code login is not available. Use paste-callback or auth.json instead."
            )
        if resp.status >= 400:
            raise CodexRatesApiError(_error_message(data, resp.status))
        user_code = data.get("user_code")
        device_auth_id = data.get("device_auth_id")
        if not isinstance(user_code, str) or not isinstance(device_auth_id, str):
            raise CodexRatesApiError("Device auth response missing fields")
        interval = int(data.get("interval") or 5)
        expires_in = int(data.get("expires_in") or 900)
        return DeviceCodeChallenge(
            verification_url=f"{OAUTH_AUTH_BASE_URL.rstrip('/')}/codex/device",
            user_code=user_code,
            device_auth_id=device_auth_id,
            interval_seconds=max(1, interval),
            expires_in_seconds=max(60, expires_in),
        )


async def poll_device_token(
    session: aiohttp.ClientSession,
    *,
    device_auth_id: str,
    user_code: str,
) -> OAuthTokens | None:
    """Poll device auth; return tokens when ready, None if still pending."""
    url = f"{OAUTH_AUTH_BASE_URL.rstrip('/')}/api/accounts/deviceauth/token"
    async with session.post(
        url,
        json={"device_auth_id": device_auth_id, "user_code": user_code},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        data = await _safe_json(resp)
        if resp.status in (403, 404):
            return None
        if resp.status >= 400:
            if _is_pending(data):
                return None
            raise CodexRatesAuthError(_error_message(data, resp.status))
        if _is_pending(data):
            return None
        if data.get("authorization_code"):
            code = data["authorization_code"]
            verifier = data.get("code_verifier")
            if not isinstance(verifier, str):
                raise CodexRatesAuthError("Device auth response missing code_verifier")
            redirect = f"{OAUTH_AUTH_BASE_URL.rstrip('/')}/deviceauth/callback"
            return await exchange_authorization_code(
                session,
                code=code,
                code_verifier=verifier,
                redirect_uri=redirect,
            )
        try:
            return _parse_tokens(data)
        except CodexRatesAuthError:
            return None


def _parse_tokens(data: dict[str, Any]) -> OAuthTokens:
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    id_token = data.get("id_token")
    if not isinstance(access, str) or not isinstance(refresh, str) or not isinstance(id_token, str):
        raise CodexRatesAuthError("OAuth response missing tokens")
    return OAuthTokens(access_token=access, refresh_token=refresh, id_token=id_token)


async def _safe_json(resp: aiohttp.ClientResponse) -> dict[str, Any]:
    try:
        data = await resp.json(content_type=None)
    except Exception:  # noqa: BLE001
        text = await resp.text()
        return {"error": {"message": text[:200]}}
    return data if isinstance(data, dict) else {"error": {"message": str(data)}}


def _error_message(data: dict[str, Any], status: int) -> str:
    err = data.get("error")
    if isinstance(err, dict):
        msg = err.get("message") or err.get("error_description")
        if isinstance(msg, str) and msg:
            return msg
    if isinstance(err, str):
        return err
    msg = data.get("message") or data.get("error_description")
    if isinstance(msg, str) and msg:
        return msg
    return f"OAuth request failed ({status})"


def _is_pending(data: dict[str, Any]) -> bool:
    err = data.get("error")
    code = None
    if isinstance(err, dict):
        code = err.get("code") or err.get("error")
    elif isinstance(err, str):
        code = err
    if code in {"authorization_pending", "slow_down"}:
        return True
    status = data.get("status")
    return isinstance(status, str) and status.lower() in {"pending", "authorization_pending"}
