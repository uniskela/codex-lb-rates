"""Config flow for Codex Rates."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    AUTH_METHOD_AUTH_JSON,
    AUTH_METHOD_DEVICE_CODE,
    AUTH_METHOD_PASTE_CALLBACK,
    AUTH_METHOD_TOKENS,
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_AUTH_JSON_PATH,
    CONF_AUTH_METHOD,
    CONF_BASE_URL,
    CONF_EMAIL,
    CONF_ID_TOKEN,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_REFRESH_TOKEN,
    CONF_RICH_SENSORS,
    CONF_TOTP_SECRET,
    CONF_VERIFY_SSL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_RICH_SENSORS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_POLL_INTERVAL,
    MODE_CHATGPT,
    MODE_CODEX_LB,
)
from .exceptions import CodexRatesApiError, CodexRatesAuthError
from .oauth import (
    exchange_authorization_code,
    parse_callback_url,
    poll_device_token,
    request_device_code,
    start_pkce_session,
)
from .providers.chatgpt import ChatGptProvider, load_auth_json, tokens_from_oauth
from .providers.codex_lb import CodexLbProvider

_LOGGER = logging.getLogger(__name__)


class CodexRatesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Codex Rates."""

    VERSION = 1

    def __init__(self) -> None:
        self._mode: str | None = None
        self._pkce = None
        self._device = None
        self._auth_method: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> CodexRatesOptionsFlow:
        return CodexRatesOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Choose integration mode."""
        if user_input is not None:
            self._mode = user_input[CONF_MODE]
            if self._mode == MODE_CODEX_LB:
                return await self.async_step_codex_lb()
            return await self.async_step_chatgpt_method()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODE, default=MODE_CODEX_LB): vol.In(
                        {
                            MODE_CODEX_LB: "Codex-LB",
                            MODE_CHATGPT: "ChatGPT / Codex CLI",
                        }
                    )
                }
            ),
        )

    async def async_step_codex_lb(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure Codex-LB connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = user_input[CONF_BASE_URL].rstrip("/")
            parsed = urlparse(base_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                errors["base"] = "invalid_url"
            else:
                session = async_get_clientsession(self.hass)
                provider = CodexLbProvider(
                    session,
                    base_url=base_url,
                    password=user_input.get(CONF_PASSWORD),
                    totp_secret=user_input.get(CONF_TOTP_SECRET),
                    verify_ssl=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                )
                try:
                    await provider.async_validate()
                except CodexRatesAuthError:
                    errors["base"] = "invalid_auth"
                except (CodexRatesApiError, aiohttp.ClientError, TimeoutError):
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected Codex-LB validation error")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(f"codex_lb:{parsed.netloc}")
                    self._abort_if_unique_id_configured()
                    title = user_input.get(CONF_NAME) or f"Codex-LB ({parsed.netloc})"
                    data = {
                        CONF_MODE: MODE_CODEX_LB,
                        CONF_BASE_URL: base_url,
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD) or "",
                        CONF_TOTP_SECRET: user_input.get(CONF_TOTP_SECRET) or "",
                        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    }
                    return self.async_create_entry(
                        title=title,
                        data=data,
                        options={
                            CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                            CONF_RICH_SENSORS: DEFAULT_RICH_SENSORS,
                        },
                    )

        return self.async_show_form(
            step_id="codex_lb",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME): str,
                    vol.Required(CONF_BASE_URL, default="http://127.0.0.1:2455"): str,
                    vol.Optional(CONF_PASSWORD, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(CONF_TOTP_SECRET, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_chatgpt_method(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose ChatGPT auth method."""
        if user_input is not None:
            self._auth_method = user_input[CONF_AUTH_METHOD]
            if self._auth_method == AUTH_METHOD_DEVICE_CODE:
                return await self.async_step_device_code()
            if self._auth_method == AUTH_METHOD_PASTE_CALLBACK:
                return await self.async_step_paste_start()
            if self._auth_method == AUTH_METHOD_AUTH_JSON:
                return await self.async_step_auth_json()
            return await self.async_step_tokens()

        return self.async_show_form(
            step_id="chatgpt_method",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_METHOD, default=AUTH_METHOD_DEVICE_CODE): vol.In(
                        {
                            AUTH_METHOD_DEVICE_CODE: "Device code (recommended)",
                            AUTH_METHOD_PASTE_CALLBACK: "Browser login + paste callback URL",
                            AUTH_METHOD_AUTH_JSON: "Import Codex CLI auth.json",
                            AUTH_METHOD_TOKENS: "Advanced: paste tokens",
                        }
                    )
                }
            ),
        )

    async def async_step_device_code(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Device-code OAuth."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)

        if self._device is None:
            try:
                self._device = await request_device_code(session)
            except CodexRatesApiError:
                return self.async_abort(reason="device_code_unavailable")
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Device code start failed")
                return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            try:
                tokens = await self._poll_device_until_done(session)
            except CodexRatesAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Device code poll failed")
                errors["base"] = "unknown"
            else:
                if tokens is None:
                    errors["base"] = "oauth_timeout"
                else:
                    return await self._async_create_chatgpt_entry(tokens_from_oauth(tokens))

        return self.async_show_form(
            step_id="device_code",
            description_placeholders={
                "verification_url": self._device.verification_url,
                "user_code": self._device.user_code,
            },
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def _poll_device_until_done(self, session: aiohttp.ClientSession):
        """Poll briefly so the HA UI is not blocked for the full device-code TTL."""
        assert self._device is not None
        # Each form submit waits up to ~45s; user can resubmit if still pending.
        deadline = asyncio.get_running_loop().time() + 45
        while asyncio.get_running_loop().time() < deadline:
            tokens = await poll_device_token(
                session,
                device_auth_id=self._device.device_auth_id,
                user_code=self._device.user_code,
            )
            if tokens is not None:
                return tokens
            await asyncio.sleep(self._device.interval_seconds)
        return None

    async def async_step_paste_start(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show authorize URL then collect callback."""
        if self._pkce is None:
            self._pkce = start_pkce_session()
        if user_input is not None:
            return await self.async_step_paste_callback()
        return self.async_show_form(
            step_id="paste_start",
            description_placeholders={"authorization_url": self._pkce.authorization_url},
            data_schema=vol.Schema({}),
        )

    async def async_step_paste_callback(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Accept pasted callback URL and exchange code."""
        errors: dict[str, str] = {}
        assert self._pkce is not None
        if user_input is not None:
            try:
                code, state = parse_callback_url(user_input["callback_url"])
                if state != self._pkce.state:
                    raise CodexRatesAuthError("OAuth state mismatch")
                session = async_get_clientsession(self.hass)
                tokens = await exchange_authorization_code(
                    session,
                    code=code,
                    code_verifier=self._pkce.code_verifier,
                )
            except CodexRatesAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Paste callback exchange failed")
                errors["base"] = "unknown"
            else:
                return await self._async_create_chatgpt_entry(tokens_from_oauth(tokens))

        return self.async_show_form(
            step_id="paste_callback",
            data_schema=vol.Schema({vol.Required("callback_url"): str}),
            errors=errors,
        )

    async def async_step_auth_json(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Import auth.json path."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                tokens = await self.hass.async_add_executor_job(
                    load_auth_json, user_input[CONF_AUTH_JSON_PATH]
                )
                session = async_get_clientsession(self.hass)
                provider = ChatGptProvider(
                    session,
                    access_token=tokens["access_token"],
                    account_id=tokens["account_id"],
                    refresh_token=tokens.get("refresh_token"),
                    id_token=tokens.get("id_token"),
                    email=tokens.get("email"),
                    auth_json_path=user_input[CONF_AUTH_JSON_PATH],
                )
                await provider.async_validate()
            except FileNotFoundError:
                errors["base"] = "auth_json_missing"
            except CodexRatesAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("auth.json validation failed")
                errors["base"] = "unknown"
            else:
                data = {
                    CONF_MODE: MODE_CHATGPT,
                    CONF_AUTH_METHOD: AUTH_METHOD_AUTH_JSON,
                    CONF_AUTH_JSON_PATH: user_input[CONF_AUTH_JSON_PATH],
                    CONF_ACCESS_TOKEN: tokens["access_token"],
                    CONF_ACCOUNT_ID: tokens["account_id"],
                    CONF_REFRESH_TOKEN: tokens.get("refresh_token", ""),
                    CONF_ID_TOKEN: tokens.get("id_token", ""),
                    CONF_EMAIL: tokens.get("email", ""),
                }
                return await self._async_create_chatgpt_entry(data)

        return self.async_show_form(
            step_id="auth_json",
            data_schema=vol.Schema(
                {vol.Required(CONF_AUTH_JSON_PATH, default="/config/.codex/auth.json"): str}
            ),
            errors=errors,
        )

    async def async_step_tokens(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Advanced manual tokens."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            provider = ChatGptProvider(
                session,
                access_token=user_input[CONF_ACCESS_TOKEN],
                account_id=user_input[CONF_ACCOUNT_ID],
                refresh_token=user_input.get(CONF_REFRESH_TOKEN),
                id_token=user_input.get(CONF_ID_TOKEN),
            )
            try:
                await provider.async_validate()
            except CodexRatesAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                data = {
                    CONF_MODE: MODE_CHATGPT,
                    CONF_AUTH_METHOD: AUTH_METHOD_TOKENS,
                    CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                    CONF_ACCOUNT_ID: user_input[CONF_ACCOUNT_ID],
                    CONF_REFRESH_TOKEN: user_input.get(CONF_REFRESH_TOKEN) or "",
                    CONF_ID_TOKEN: user_input.get(CONF_ID_TOKEN) or "",
                }
                return await self._async_create_chatgpt_entry(data)

        return self.async_show_form(
            step_id="tokens",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Required(CONF_ACCOUNT_ID): str,
                    vol.Optional(CONF_REFRESH_TOKEN, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(CONF_ID_TOKEN, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def _async_create_chatgpt_entry(self, data: dict[str, Any]) -> FlowResult:
        account_id = data[CONF_ACCOUNT_ID]
        await self.async_set_unique_id(f"chatgpt:{account_id}")
        self._abort_if_unique_id_configured()
        payload = {CONF_MODE: MODE_CHATGPT, **data}
        if CONF_AUTH_METHOD not in payload and self._auth_method:
            payload[CONF_AUTH_METHOD] = self._auth_method
        title = data.get(CONF_EMAIL) or f"ChatGPT ({account_id[:8]})"
        return self.async_create_entry(
            title=title,
            data=payload,
            options={
                CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                CONF_RICH_SENSORS: DEFAULT_RICH_SENSORS,
            },
        )


class CodexRatesOptionsFlow(config_entries.OptionsFlow):
    """Options flow for poll interval and rich sensors."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow with config entry reference."""
        # Avoid assigning to self.config_entry — newer HA injects it read-only.
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry = self._config_entry
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=3600)),
                    vol.Required(
                        CONF_RICH_SENSORS,
                        default=entry.options.get(CONF_RICH_SENSORS, DEFAULT_RICH_SENSORS),
                    ): bool,
                }
            ),
        )
