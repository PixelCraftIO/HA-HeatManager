"""Pause switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeatManagerConfigEntry
from .entity import HeatManagerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: HeatManagerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([PauseSwitch(entry.runtime_data)])


class PauseSwitch(HeatManagerEntity, SwitchEntity):
    """On while the schedule is paused. Use the pause action for a time limit."""

    _attr_translation_key = "pause"
    _attr_icon = "mdi:calendar-remove"

    def __init__(self, manager) -> None:
        super().__init__(manager, None, "pause")

    @property
    def is_on(self) -> bool:
        return self.manager.pause_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        until = self.manager.pause_until
        return {"until": until.isoformat() if until else None}

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.manager.set_pause(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.manager.set_pause(False)
