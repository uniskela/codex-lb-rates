"""DataUpdateCoordinator for Codex Rates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from math import ceil, isfinite

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
    CONF_LB_LOGIN,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_REFRESH_TOKEN,
    CONF_TOTP_SECRET,
    CONF_VERIFY_SSL,
    DEFAULT_LB_LOGIN,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_RATE_LIMIT_COOLDOWN,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MAX_RATE_LIMIT_COOLDOWN,
    MIN_POLL_INTERVAL,
    MODE_CODEX_LB,
)
from .exceptions import (
    CodexRatesApiError,
    CodexRatesAuthError,
    CodexRatesRateLimitError,
)
from .models import ProviderSnapshot
from .providers.chatgpt import ChatGptProvider
from .providers.codex_lb import CodexLbProvider

_LOGGER = logging.getLogger(__name__)
_COOLDOWNS = f"{DOMAIN}_cooldowns"


class CodexRatesCoordinator(DataUpdateCoordinator[ProviderSnapshot]):
    """Poll the configured quota provider."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = entry.options.get(
            CONF_POLL_INTERVAL,
            entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )
        self.poll_interval_seconds = max(MIN_POLL_INTERVAL, int(interval))
        self.last_successful_poll_at: datetime | None = None
        self.rate_limit_cooldown_until: datetime | None = None
        self.last_rate_limit_at: datetime | None = None
        self.last_rate_limit_retry_after: float | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.poll_interval_seconds),
            config_entry=entry,
        )
        # Explicit so cooldown logic works under HA stubs and after temporary backoff.
        self.update_interval = timedelta(seconds=self.poll_interval_seconds)
        self.entry = entry
        # Keep active deadlines outside the coordinator: HA recreates it on
        # options reload and when retrying a failed first refresh.
        self._cooldowns = hass.data.setdefault(_COOLDOWNS, {})
        if saved := self._cooldowns.get(entry.entry_id):
            (
                self.rate_limit_cooldown_until,
                self.last_rate_limit_at,
                self.last_rate_limit_retry_after,
            ) = saved
            remaining = (
                self.rate_limit_cooldown_until - datetime.now(timezone.utc)
            ).total_seconds()
            if remaining > 0:
                self.update_interval = timedelta(seconds=ceil(remaining))
            else:
                self._clear_rate_limit_cooldown()
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
                login_mode=self.entry.data.get(CONF_LB_LOGIN, DEFAULT_LB_LOGIN),
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

    def _cooldown_seconds(self, retry_after: float | None) -> int:
        raw = DEFAULT_RATE_LIMIT_COOLDOWN if retry_after is None else float(retry_after)
        if not isfinite(raw) or raw < 0:
            raw = DEFAULT_RATE_LIMIT_COOLDOWN
        return max(MIN_POLL_INTERVAL, min(ceil(raw), MAX_RATE_LIMIT_COOLDOWN))

    def _apply_rate_limit_cooldown(self, err: CodexRatesRateLimitError) -> int:
        """Stretch poll interval and record skip-until for an HTTP 429."""
        now = datetime.now(timezone.utc)
        seconds = self._cooldown_seconds(err.retry_after)
        self.last_rate_limit_at = now
        self.last_rate_limit_retry_after = err.retry_after
        self.rate_limit_cooldown_until = now + timedelta(seconds=seconds)
        self._cooldowns[self.entry.entry_id] = (
            self.rate_limit_cooldown_until, now, err.retry_after
        )
        self.update_interval = timedelta(seconds=seconds)
        _LOGGER.warning(
            "Provider HTTP rate limited (429); cooling down for %ss until %s "
            "(distinct from account status rate_limited)",
            seconds,
            self.rate_limit_cooldown_until.isoformat(),
        )
        return seconds

    def _clear_rate_limit_cooldown(self) -> None:
        """Restore the configured poll interval after a successful fetch."""
        self.rate_limit_cooldown_until = None
        self._cooldowns.pop(self.entry.entry_id, None)
        self.update_interval = timedelta(seconds=self.poll_interval_seconds)

    def _rate_limit_update_failed(self, *, remaining_seconds: int | None = None) -> UpdateFailed:
        until = self.rate_limit_cooldown_until
        until_text = until.isoformat() if until is not None else "unknown"
        if remaining_seconds is None and until is not None:
            remaining_seconds = max(
                1, ceil((until - datetime.now(timezone.utc)).total_seconds())
            )
        remaining_text = (
            f"{remaining_seconds}s remaining; " if remaining_seconds is not None else ""
        )
        return UpdateFailed(
            f"Provider HTTP rate limited (429); {remaining_text}"
            f"cooldown until {until_text}. "
            "This is a temporary poll backoff, not account status 'rate_limited'."
        )

    async def _async_update_data(self) -> ProviderSnapshot:
        now = datetime.now(timezone.utc)
        if (
            self.rate_limit_cooldown_until is not None
            and now < self.rate_limit_cooldown_until
        ):
            remaining = max(
                1, ceil((self.rate_limit_cooldown_until - now).total_seconds())
            )
            # Keep interval aligned with remaining cooldown for the next schedule.
            self.update_interval = timedelta(seconds=remaining)
            raise self._rate_limit_update_failed(remaining_seconds=remaining)

        if (
            self.rate_limit_cooldown_until is not None
            and now >= self.rate_limit_cooldown_until
        ):
            # Cooldown elapsed; drop the stamp before attempting a fresh poll.
            self._clear_rate_limit_cooldown()

        if self._provider is None:
            self._provider = self._build_provider()
        try:
            snapshot = await self._provider.async_fetch()
            now = datetime.now(timezone.utc)
            self.last_successful_poll_at = now
            self._clear_rate_limit_cooldown()
            # ChatGPT usage payloads often omit last_refresh; fall back to poll time.
            if self.entry.data.get(CONF_MODE) != MODE_CODEX_LB:
                for account in snapshot.accounts:
                    if account.last_refresh_at is None:
                        account.last_refresh_at = now
            return snapshot
        except CodexRatesAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CodexRatesRateLimitError as err:
            seconds = self._apply_rate_limit_cooldown(err)
            raise self._rate_limit_update_failed(remaining_seconds=seconds) from err
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
