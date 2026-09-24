"""Tests for bundled Lovelace card registration helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.codex_rates import lovelace as lovelace_mod


def test_card_bundle_exists() -> None:
    """The www card module must ship with the integration package."""
    card = Path(lovelace_mod.__file__).parent / "www" / lovelace_mod.CARD_FILENAME
    assert card.is_file()
    text = card.read_text(encoding="utf-8")
    assert "codex-rates-card" in text
    assert "customElements.define" in text
    assert "getConfigForm" in text
    assert "computeLabel" in text
    assert "assertConfig" in text
    assert "Primary remaining entity" in text


def test_card_digest_is_stable_for_same_bytes(tmp_path: Path) -> None:
    path = tmp_path / "card.js"
    path.write_text("console.log('codex');\n", encoding="utf-8")
    assert lovelace_mod._card_digest(path) == lovelace_mod._card_digest(path)
    assert len(lovelace_mod._card_digest(path)) == 8


def _install_frontend_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    with_lovelace_data: bool = True,
    with_static_path_config: bool = True,
) -> tuple[MagicMock, type | None]:
    """Install minimal homeassistant.components stubs used by lovelace.py."""
    add_extra_js_url = MagicMock()
    ResourceStorageCollection: type | None = None

    if with_static_path_config:
        http_mod = ModuleType("homeassistant.components.http")

        class StaticPathConfig:
            def __init__(self, url_path, path, cache_headers):  # noqa: ANN001
                self.url_path = url_path
                self.path = path
                self.cache_headers = cache_headers

        http_mod.StaticPathConfig = StaticPathConfig  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "homeassistant.components.http", http_mod)
    else:
        sys.modules.pop("homeassistant.components.http", None)

    frontend_mod = ModuleType("homeassistant.components.frontend")
    frontend_mod.add_extra_js_url = add_extra_js_url  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "homeassistant.components.frontend", frontend_mod)

    if with_lovelace_data:
        lovelace_pkg = ModuleType("homeassistant.components.lovelace")
        lovelace_pkg.LOVELACE_DATA = "lovelace"  # type: ignore[attr-defined]
        monkeypatch.setitem(
            sys.modules, "homeassistant.components.lovelace", lovelace_pkg
        )

        class ResourceStorageCollection:
            """Marker class matching what lovelace.py imports."""

        resources_mod = ModuleType("homeassistant.components.lovelace.resources")
        resources_mod.ResourceStorageCollection = ResourceStorageCollection  # type: ignore[attr-defined]
        monkeypatch.setitem(
            sys.modules, "homeassistant.components.lovelace.resources", resources_mod
        )
    else:
        sys.modules.pop("homeassistant.components.lovelace", None)
        sys.modules.pop("homeassistant.components.lovelace.resources", None)

    components = sys.modules.setdefault(
        "homeassistant.components", ModuleType("homeassistant.components")
    )
    monkeypatch.setattr(components, "frontend", frontend_mod, raising=False)

    return add_extra_js_url, ResourceStorageCollection


def _card_url() -> str:
    digest = lovelace_mod._card_digest(
        Path(lovelace_mod.__file__).parent / "www" / lovelace_mod.CARD_FILENAME
    )
    return f"{lovelace_mod.CARD_URL_BASE}/{lovelace_mod.CARD_FILENAME}?v={digest}"


@pytest.mark.asyncio
async def test_async_setup_lovelace_card_registers_static_path_and_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage-mode Lovelace should get a module resource with a digest query."""
    add_extra_js_url, ResourceStorageCollection = _install_frontend_stubs(monkeypatch)
    assert ResourceStorageCollection is not None
    created: list[dict] = []

    class FakeResources(ResourceStorageCollection):
        def __init__(self) -> None:
            self._items: list[dict] = []

        async def async_get_info(self) -> dict:
            return {}

        def async_items(self):
            return list(self._items)

        async def async_create_item(self, data: dict) -> None:
            created.append(data)
            self._items.append({"id": "1", **data})

        async def async_update_item(self, item_id: str, data: dict) -> None:
            raise AssertionError("unexpected update")

    registered_paths: list = []

    async def capture_paths(configs):  # noqa: ANN001
        registered_paths.extend(configs)

    hass = SimpleNamespace(
        data={"lovelace": SimpleNamespace(resources=FakeResources())},
        http=SimpleNamespace(
            async_register_static_paths=AsyncMock(side_effect=capture_paths)
        ),
        async_add_executor_job=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
    )

    await lovelace_mod.async_setup_lovelace_card(hass)
    await lovelace_mod.async_setup_lovelace_card(hass)  # idempotent on same digest

    hass.http.async_register_static_paths.assert_awaited_once()
    assert registered_paths
    assert registered_paths[0].url_path == lovelace_mod.CARD_URL_BASE
    assert len(created) == 1
    assert created[0]["res_type"] == "module"
    assert created[0]["url"] == _card_url()
    add_extra_js_url.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("same_url", [False, True])
async def test_async_setup_lovelace_card_updates_stale_resource(
    monkeypatch: pytest.MonkeyPatch,
    same_url: bool,
) -> None:
    _, ResourceStorageCollection = _install_frontend_stubs(monkeypatch)
    assert ResourceStorageCollection is not None
    updated: list[tuple[str, dict]] = []

    class FakeResources(ResourceStorageCollection):
        def __init__(self) -> None:
            self._items = [
                {
                    "id": "res-1",
                    "type": "js" if same_url else "module",
                    "url": _card_url() if same_url else (
                        f"{lovelace_mod.CARD_URL_BASE}/"
                        f"{lovelace_mod.CARD_FILENAME}?v=oldoldol"
                    ),
                }
            ]

        async def async_get_info(self) -> dict:
            return {}

        def async_items(self):
            return list(self._items)

        async def async_create_item(self, data: dict) -> None:
            raise AssertionError("should update existing resource")

        async def async_update_item(self, item_id: str, data: dict) -> None:
            updated.append((item_id, data))
            self._items[0] = {"id": item_id, **data}

    hass = SimpleNamespace(
        data={
            lovelace_mod._CARD_STATIC_PATH_KEY: True,
            "lovelace": SimpleNamespace(resources=FakeResources()),
        },
        http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        async_add_executor_job=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
    )

    await lovelace_mod.async_setup_lovelace_card(hass)

    assert updated == [
        (
            "res-1",
            {"res_type": "module", "url": _card_url()},
        )
    ]


@pytest.mark.asyncio
async def test_retries_upgrade_from_extra_js_to_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Early setup without Lovelace must not poison later storage registration."""
    add_extra_js_url, ResourceStorageCollection = _install_frontend_stubs(monkeypatch)
    assert ResourceStorageCollection is not None
    created: list[dict] = []

    class FakeResources(ResourceStorageCollection):
        def __init__(self) -> None:
            self._items: list[dict] = []

        async def async_get_info(self) -> dict:
            return {}

        def async_items(self):
            return list(self._items)

        async def async_create_item(self, data: dict) -> None:
            created.append(data)
            self._items.append({"id": "1", **data})

        async def async_update_item(self, item_id: str, data: dict) -> None:
            raise AssertionError("unexpected update")

    hass = SimpleNamespace(
        data={},
        http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        async_add_executor_job=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
    )

    await lovelace_mod.async_setup_lovelace_card(hass)
    assert add_extra_js_url.call_count == 1
    assert created == []
    assert lovelace_mod._CARD_STORAGE_RESOURCE_KEY not in hass.data

    hass.data["lovelace"] = SimpleNamespace(resources=FakeResources())
    await lovelace_mod.async_setup_lovelace_card(hass)

    assert created == [{"res_type": "module", "url": _card_url()}]
    assert hass.data[lovelace_mod._CARD_STORAGE_RESOURCE_KEY] == _card_url()


@pytest.mark.asyncio
async def test_without_lovelace_data_still_injects_frontend_js(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-LOVELACE_DATA HA should still get add_extra_js_url, not a silent skip."""
    add_extra_js_url, _ = _install_frontend_stubs(
        monkeypatch, with_lovelace_data=False
    )

    hass = SimpleNamespace(
        data={lovelace_mod._CARD_STATIC_PATH_KEY: True},
        http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        async_add_executor_job=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
    )

    await lovelace_mod.async_setup_lovelace_card(hass)

    add_extra_js_url.assert_called_once_with(hass, _card_url())
    assert lovelace_mod._CARD_STORAGE_RESOURCE_KEY not in hass.data


@pytest.mark.asyncio
async def test_dict_shaped_lovelace_resources_pre_2025_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Older hass.data['lovelace'] dict layout must still create a storage resource."""
    add_extra_js_url, ResourceStorageCollection = _install_frontend_stubs(
        monkeypatch, with_lovelace_data=False
    )

    # Provide ResourceStorageCollection without LOVELACE_DATA.
    class ResourceStorageCollection:
        pass

    resources_mod = ModuleType("homeassistant.components.lovelace.resources")
    resources_mod.ResourceStorageCollection = ResourceStorageCollection  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "homeassistant.components.lovelace.resources", resources_mod
    )
    # lovelace package import should fail so code uses hass.data["lovelace"] dict.
    sys.modules.pop("homeassistant.components.lovelace", None)

    created: list[dict] = []

    class FakeResources(ResourceStorageCollection):
        def __init__(self) -> None:
            self._items: list[dict] = []

        async def async_get_info(self) -> dict:
            return {}

        def async_items(self):
            return list(self._items)

        async def async_create_item(self, data: dict) -> None:
            created.append(data)
            self._items.append({"id": "1", **data})

        async def async_update_item(self, item_id: str, data: dict) -> None:
            raise AssertionError("unexpected update")

    hass = SimpleNamespace(
        data={
            lovelace_mod._CARD_STATIC_PATH_KEY: True,
            "lovelace": {"resources": FakeResources()},
        },
        http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        async_add_executor_job=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
    )

    await lovelace_mod.async_setup_lovelace_card(hass)

    assert created == [{"res_type": "module", "url": _card_url()}]
    add_extra_js_url.assert_not_called()


@pytest.mark.asyncio
async def test_legacy_register_static_path_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HA without StaticPathConfig should use register_static_path."""
    add_extra_js_url, _ = _install_frontend_stubs(
        monkeypatch, with_static_path_config=False, with_lovelace_data=False
    )
    register_static_path = MagicMock()

    hass = SimpleNamespace(
        data={},
        http=SimpleNamespace(
            register_static_path=register_static_path,
            async_register_static_paths=None,
        ),
        async_add_executor_job=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
    )

    await lovelace_mod.async_setup_lovelace_card(hass)

    register_static_path.assert_called_once()
    assert register_static_path.call_args.args[0] == lovelace_mod.CARD_URL_BASE
    add_extra_js_url.assert_called_once()


@pytest.mark.asyncio
async def test_card_setup_errors_do_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Card registration failures must not abort integration setup."""
    _install_frontend_stubs(monkeypatch)
    hass = SimpleNamespace(
        data={},
        http=SimpleNamespace(
            async_register_static_paths=AsyncMock(side_effect=RuntimeError("boom"))
        ),
        async_add_executor_job=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
    )

    await lovelace_mod.async_setup_lovelace_card(hass)
