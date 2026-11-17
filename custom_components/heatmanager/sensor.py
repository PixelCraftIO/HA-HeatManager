"""Target temperature per room."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeatManagerConfigEntry
from .entity import HeatManagerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: HeatManagerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    manager = entry.runtime_data
    async_add_entities(RoomTargetSensor(manager, room) for room in manager.rooms.values())


class RoomTargetSensor(HeatManagerEntity, SensorEntity):
    """The temperature HeatManager wants for the room (unknown when it leaves it alone)."""

    _attr_translation_key = "target"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, manager, room) -> None:
        super().__init__(manager, room, "target")

    @property
    def native_value(self) -> float | None:
        return self.manager.runtime[self.room.id].target

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self.manager.room_info(self.room)
        profile = self.manager.profiles.get(info["profile"])
        return {
            "reason": info["reason"],
            "profile": profile["name"] if profile else info["profile"],
            "window_open": info["window_open"],
            "next_change": info["next_change"],
            "next_temperature": info["next_temp"],
            "override_until": info["override"]["until"] if info["override"] else None,
        }
