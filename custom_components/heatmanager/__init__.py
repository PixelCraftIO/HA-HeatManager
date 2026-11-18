"""HeatManager: weekly heating profiles, window detection and pause for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import CARD_FILENAME, DOMAIN, FRONTEND_URL, NAME, STORAGE_KEY, STORAGE_VERSION, VERSION
from .loader import async_ensure_loader, async_remove_loader
from .manager import HeatManager, get_manager
from .websocket import async_register_websocket

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_PAUSE = "pause"
SERVICE_RESUME = "resume"
SERVICE_OVERRIDE = "override_room"
SERVICE_CLEAR_OVERRIDE = "clear_room_override"
SERVICE_START_VACATION = "start_vacation"
SERVICE_END_VACATION = "end_vacation"

PAUSE_SCHEMA = vol.Schema(
    {
        vol.Exclusive("duration", "end"): cv.positive_time_period,
        vol.Exclusive("until", "end"): cv.datetime,
    }
)

OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Required("room"): cv.string,
        vol.Required("temperature"): vol.Coerce(float),
        vol.Exclusive("duration", "end"): cv.positive_time_period,
        vol.Exclusive("until", "end"): cv.datetime,
        vol.Exclusive("until_next_change", "end"): cv.boolean,
    }
)
CLEAR_OVERRIDE_SCHEMA = vol.Schema({vol.Required("room"): cv.string})
VACATION_SCHEMA = vol.Schema({vol.Required("until"): cv.datetime})

type HeatManagerConfigEntry = ConfigEntry[HeatManager]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the card, websocket commands and services once."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)
    async_register_websocket(hass)

    async def _pause(call: ServiceCall) -> None:
        manager = _manager(hass)
        until = None
        if (duration := call.data.get("duration")) is not None:
            until = dt_util.now() + duration
        elif (moment := call.data.get("until")) is not None:
            until = dt_util.as_local(
                moment if moment.tzinfo else moment.replace(tzinfo=dt_util.get_default_time_zone())
            )
        if until is not None and until <= dt_util.now():
            raise ServiceValidationError("The end of the pause must be in the future")
        manager.set_pause(True, until)

    async def _resume(call: ServiceCall) -> None:
        _manager(hass).set_pause(False)

    async def _override(call: ServiceCall) -> None:
        manager = _manager(hass)
        room_id = _room_id(manager, call.data["room"])
        until = None
        if (duration := call.data.get("duration")) is not None:
            until = dt_util.now() + duration
        elif (moment := call.data.get("until")) is not None:
            until = dt_util.as_local(
                moment if moment.tzinfo else moment.replace(tzinfo=dt_util.get_default_time_zone())
            )
        try:
            manager.set_override(
                room_id, call.data["temperature"], until, until_next_change=call.data.get("until_next_change", False)
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def _clear_override(call: ServiceCall) -> None:
        manager = _manager(hass)
        manager.clear_override(_room_id(manager, call.data["room"]))

    async def _start_vacation(call: ServiceCall) -> None:
        moment = call.data["until"]
        until = dt_util.as_local(moment if moment.tzinfo else moment.replace(tzinfo=dt_util.get_default_time_zone()))
        try:
            _manager(hass).set_vacation(until)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def _end_vacation(call: ServiceCall) -> None:
        _manager(hass).set_vacation(None)

    hass.services.async_register(DOMAIN, SERVICE_START_VACATION, _start_vacation, schema=VACATION_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_END_VACATION, _end_vacation)
    hass.services.async_register(DOMAIN, SERVICE_PAUSE, _pause, schema=PAUSE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_OVERRIDE, _override, schema=OVERRIDE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_OVERRIDE, _clear_override, schema=CLEAR_OVERRIDE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RESUME, _resume)
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card and load it on every dashboard (no manual resource needed)."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(Path(__file__).parent / "frontend"), False)]
    )
    add_extra_js_url(hass, f"{FRONTEND_URL}/{CARD_FILENAME}?v={VERSION}")
    # pages opened while Home Assistant is still starting miss the line above
    await async_ensure_loader(hass)


def _manager(hass: HomeAssistant) -> HeatManager:
    try:
        return get_manager(hass)
    except LookupError as err:
        raise ServiceValidationError("HeatManager is not set up") from err


def _room_id(manager: HeatManager, value: str) -> str:
    """Find a room by id or name."""
    if value in manager.rooms:
        return value
    for room in manager.rooms.values():
        if room.name.casefold() == value.strip().casefold():
            return room.id
    raise ServiceValidationError(f"Unknown room {value}")


async def async_setup_entry(hass: HomeAssistant, entry: HeatManagerConfigEntry) -> bool:
    """Set up HeatManager from a config entry."""
    manager = HeatManager(hass, entry)
    await manager.async_load()
    entry.runtime_data = manager
    hass.data[DOMAIN][entry.entry_id] = manager
    # Parent device first, room devices refer to it
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=NAME,
        manufacturer="PixelDevIO",
        model="HeatManager",
        sw_version=VERSION,
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await manager.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: HeatManagerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HeatManagerConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.async_stop()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: HeatManagerConfigEntry) -> None:
    """Remove stored profiles when the integration is deleted."""
    await Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}").async_remove()
    await async_remove_loader(hass)
