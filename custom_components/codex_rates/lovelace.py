"""Register the bundled Lovelace card from ``www/``."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "codex-rates-card.js"
CARD_URL_BASE = f"/{DOMAIN}"
_CARD_STATIC_PATH_KEY = f"{DOMAIN}_card_static_path"
_CARD_STORAGE_RESOURCE_KEY = f"{DOMAIN}_card_storage_resource"
_CARD_EXTRA_JS_KEY = f"{DOMAIN}_card_extra_js"


def _card_digest(path: Path) -> str:
    """Return a short content hash for cache-busting the card URL."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


async def async_setup_lovelace_card(hass: HomeAssistant) -> None:
    """Serve ``www/`` and ensure the card is loadable as a Lovelace module.

    Storage-mode Lovelace gets a persisted resource with a content-hash ``?v=``
    query so browsers pick up updates after HACS upgrades. YAML-mode resources
    are read-only to integrations, so we fall back to ``add_extra_js_url``.

    Compatible with HA 2024.1+ (legacy static-path + dict Lovelace data) and
    newer releases (``StaticPathConfig`` / ``LOVELACE_DATA``).
    """
    try:
        await _async_setup_lovelace_card(hass)
    except Exception:  # noqa: BLE001 — card must never block the integration
        _LOGGER.exception(
            "Failed to register bundled Lovelace card; add /%s/%s manually",
            DOMAIN,
            CARD_FILENAME,
        )


async def _async_setup_lovelace_card(hass: HomeAssistant) -> None:
    www_dir = Path(__file__).parent / "www"
    if not www_dir.is_dir():
        _LOGGER.warning("Lovelace card directory missing: %s", www_dir)
        return

    if not await _async_register_static_path(hass, www_dir):
        return

    card_path = www_dir / CARD_FILENAME
    try:
        digest = await hass.async_add_executor_job(_card_digest, card_path)
    except OSError:
        _LOGGER.exception("Lovelace card bundle missing or unreadable: %s", card_path)
        return

    base_url = f"{CARD_URL_BASE}/{CARD_FILENAME}"
    url = f"{base_url}?v={digest}"

    if hass.data.get(_CARD_STORAGE_RESOURCE_KEY) == url:
        return

    registered_storage = await _async_register_resource(
        hass, base_url=base_url, url=url
    )
    if registered_storage:
        hass.data[_CARD_STORAGE_RESOURCE_KEY] = url


async def _async_register_static_path(hass: HomeAssistant, www_dir: Path) -> bool:
    """Expose ``www/`` at ``CARD_URL_BASE``. Returns False if serving failed."""
    if hass.data.get(_CARD_STATIC_PATH_KEY):
        return True

    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_BASE, str(www_dir), False)]
        )
    except (ImportError, AttributeError):
        register = getattr(hass.http, "register_static_path", None)
        if register is None:
            _LOGGER.warning(
                "HTTP static path APIs unavailable; cannot serve Lovelace card"
            )
            return False
        register(CARD_URL_BASE, str(www_dir), False)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to register Lovelace card static path")
        return False

    hass.data[_CARD_STATIC_PATH_KEY] = True
    return True


def _lovelace_resources(hass: HomeAssistant) -> Any | None:
    """Return the Lovelace resources collection when available."""
    try:
        from homeassistant.components.lovelace import LOVELACE_DATA

        lovelace_data = hass.data.get(LOVELACE_DATA)
    except ImportError:
        lovelace_data = hass.data.get("lovelace")

    if lovelace_data is None:
        return None
    if isinstance(lovelace_data, dict):
        return lovelace_data.get("resources")
    return getattr(lovelace_data, "resources", None)


def _is_storage_collection(resources: Any) -> bool:
    """True when resources can be created/updated by the integration."""
    try:
        from homeassistant.components.lovelace.resources import (
            ResourceStorageCollection,
        )
    except ImportError:
        return False
    return isinstance(resources, ResourceStorageCollection)


async def _async_register_resource(
    hass: HomeAssistant, *, base_url: str, url: str
) -> bool:
    """Create/update a storage resource, or inject via frontend.

    Returns True only when a storage-mode Lovelace resource is present at
    ``url`` (so later retries can upgrade from frontend injection).
    """
    resources = _lovelace_resources(hass)

    if resources is not None and _is_storage_collection(resources):
        await resources.async_get_info()
        for item in resources.async_items():
            item_url = item.get("url", "")
            if item_url.partition("?")[0] != base_url:
                continue
            if item_url != url:
                await resources.async_update_item(
                    item["id"], {"res_type": "module", "url": url}
                )
                _LOGGER.debug("Updated Lovelace card resource to %s", url)
            return True
        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.debug("Created Lovelace card resource %s", url)
        return True

    await _async_add_extra_js(hass, url)
    if resources is None:
        _LOGGER.debug(
            "Lovelace resources not ready; injected card via frontend: %s", url
        )
    else:
        _LOGGER.debug(
            "Lovelace resources are YAML-managed; registered card via frontend: %s",
            url,
        )
    return False


async def _async_add_extra_js(hass: HomeAssistant, url: str) -> None:
    """Inject the module once per digest via frontend extra JS URLs."""
    if hass.data.get(_CARD_EXTRA_JS_KEY) == url:
        return
    try:
        from homeassistant.components.frontend import add_extra_js_url
    except ImportError:
        _LOGGER.debug(
            "Frontend not available; card served at %s (add Lovelace resource manually)",
            url,
        )
        return
    add_extra_js_url(hass, url)
    hass.data[_CARD_EXTRA_JS_KEY] = url
