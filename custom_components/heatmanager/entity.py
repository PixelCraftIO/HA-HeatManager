"""Shared entity base."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME, SIGNAL_UPDATE, VERSION
from .manager import HeatManager, Room


class HeatManagerEntity(Entity):
    """Updates whenever the manager signals a change."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: HeatManager, room: Room | None, key: str) -> None:
        self.manager = manager
        self.room = room
        entry_id = manager.entry.entry_id
        if room is None:
            self._attr_unique_id = f"{entry_id}_{key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry_id)},
                name=NAME,
                manufacturer="PixelDevIO",
                model="HeatManager",
                sw_version=VERSION,
                entry_type=DeviceEntryType.SERVICE,
            )
        else:
            self._attr_unique_id = f"{entry_id}_{room.id}_{key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_{room.id}")},
                # short names: "Kids Heating profile" instead of "HeatManager Kids Heating profile"
                name=room.name,
                manufacturer="PixelDevIO",
                model="HeatManager room",
                suggested_area=room.area_name,
                entry_type=DeviceEntryType.SERVICE,
            )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"{SIGNAL_UPDATE}_{self.manager.entry.entry_id}", self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
