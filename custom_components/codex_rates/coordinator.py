"""DataUpdateCoordinator for Codex Rates."""

from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_AUTH_JSON_PATH,
    CONF_BASE_URL,
    CONF_EMAIL,
    CONF_ID_TOKEN,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_REFRESH_TOKEN,
    CONF_TOTP_SECRET,
    CONF_VERIFY_SSL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MODE_CODEX_LB,
)
from .exceptions import CodexRatesApiError, CodexRatesAuthError
from .models import ProviderSnapshot
from .providers.chatgpt import ChatGptProvider
from .providers.codex_lb import CodexLbProvider

_LOGGER = logging.getLogger(__name__)


class CodexRatesCoordinator(DataUpdateCoordinator[ProviderSnapshot]):
    """Poll the configured quota provider."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = entry.options.get(
            CONF_POLL_INTERVAL,
            entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=max(30, int(interval))),
            config_entry=entry,
        )
        self.entry = entry
        self._provider: CodexLbProvider | ChatGptProvider | None = None
        # Private session for Codex-LB so dashboard cookies never enter the shared HA jar.
        self._lb_session: aiohttp.ClientSession | None = None

    def _build_provider(self) -> CodexLbProvider | ChatGptProvider:
        mode = self.entry.data[CONF_MODE]
        if mode == MODE_CODEX_LB:
            if self._lb_session is None or self._lb_session.closed:
                verify_ssl = self.entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
                try:
                    self._lb_session = async_create_clientsession(
                        self.hass,
                        verify_ssl=verify_ssl,
                        auto_cleanup=False,
                    )
                except TypeError:
                    # Older Home Assistant builds may not accept auto_cleanup.
                    self._lb_session = async_create_clientsession(
                        self.hass,
                        verify_ssl=verify_ssl,
                    )
            return CodexLbProvider(
                self._lb_session,
                base_url=self.entry.data[CONF_BASE_URL],
                password=self.entry.data.get(CONF_PASSWORD),
                totp_secret=self.entry.data.get(CONF_TOTP_SECRET),
                verify_ssl=self.entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            )

        async def _persist(tokens: dict[str, str]) -> None:
            data = {**self.entry.data}
            for key in (
                CONF_ACCESS_TOKEN,
                CONF_REFRESH_TOKEN,
                CONF_ID_TOKEN,
                CONF_ACCOUNT_ID,
                CONF_EMAIL,
            ):
                if key in tokens and tokens[key]:
                    data[key] = tokens[key]
            self.hass.config_entries.async_update_entry(self.entry, data=data)

        # ChatGPT uses the shared session (Bearer auth only; no Set-Cookie login).
        return ChatGptProvider(
            async_get_clientsession(self.hass),
            access_token=self.entry.data[CONF_ACCESS_TOKEN],
            account_id=self.entry.data[CONF_ACCOUNT_ID],
            refresh_token=self.entry.data.get(CONF_REFRESH_TOKEN),
            id_token=self.entry.data.get(CONF_ID_TOKEN),
            email=self.entry.data.get(CONF_EMAIL),
            auth_json_path=self.entry.data.get(CONF_AUTH_JSON_PATH),
            on_tokens_updated=_persist,
        )

    async def _async_update_data(self) -> ProviderSnapshot:
        if self._provider is None:
            self._provider = self._build_provider()
        try:
            return await self._provider.async_fetch()
        except CodexRatesAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CodexRatesApiError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(str(err)) from err

    def rebuild_provider(self) -> None:
        """Drop cached provider after options/data change."""
        self._provider = None

    async def async_shutdown_provider(self) -> None:
        """Close privately owned HTTP sessions."""
        self._provider = None
        if self._lb_session is not None and not self._lb_session.closed:
            await self._lb_session.close()
        self._lb_session = None
