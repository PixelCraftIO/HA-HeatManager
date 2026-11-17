"""The card loader resource for dashboards opened while Home Assistant starts."""

from __future__ import annotations

from urllib.parse import unquote

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest

from custom_components.heatmanager.const import VERSION
from custom_components.heatmanager.loader import async_ensure_loader, async_remove_loader, is_loader, loader_url


@pytest.fixture
async def resources(hass: HomeAssistant):
    assert await async_setup_component(hass, "lovelace", {})
    collection = hass.data[LOVELACE_DATA].resources
    await collection.async_load()
    collection.loaded = True
    return collection


def ours(resources) -> list[dict]:
    return [item for item in resources.async_items() if is_loader(item)]


def test_loader_url() -> None:
    url = loader_url()
    assert url.startswith("data:text/javascript,")
    assert f"/heatmanager_static/heatmanager-card.js?v={VERSION}" in unquote(url)
    assert "#" not in url and "\n" not in url


async def test_loader_added_once_and_kept_current(hass: HomeAssistant, resources) -> None:
    await resources.async_create_item({"res_type": "module", "url": "/local/other-card.js"})
    await async_ensure_loader(hass)
    await async_ensure_loader(hass)
    assert len(ours(resources)) == 1
    assert ours(resources)[0]["url"] == loader_url()
    assert ours(resources)[0]["type"] == "module"
    # an older version is updated in place, duplicates are removed
    old = loader_url().replace(VERSION, "0.0.1")
    item_id = ours(resources)[0]["id"]
    await resources.async_update_item(item_id, {"url": old})
    await resources.async_create_item({"res_type": "module", "url": old})
    await async_ensure_loader(hass)
    assert [i["id"] for i in ours(resources)] == [item_id]
    assert ours(resources)[0]["url"] == loader_url()
    # other resources are never touched
    assert any(i["url"] == "/local/other-card.js" for i in resources.async_items())
    await async_remove_loader(hass)
    assert ours(resources) == []
    assert len(resources.async_items()) == 1


async def test_yaml_resources_are_left_alone(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"resource_mode": "yaml"}})
    await async_ensure_loader(hass)
    assert not any(is_loader(i) for i in hass.data[LOVELACE_DATA].resources.async_items())


async def test_without_lovelace_nothing_happens(hass: HomeAssistant) -> None:
    await async_ensure_loader(hass)
    await async_remove_loader(hass)
