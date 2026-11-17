"""Profile selection per room."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeatManagerConfigEntry
from .const import ASSIGN_FROST, ASSIGN_MANUAL
from .entity import HeatManagerEntity

LABELS = {
    "de": {ASSIGN_FROST: "Frostschutz", ASSIGN_MANUAL: "Manuell"},
    "en": {ASSIGN_FROST: "Frost protection", ASSIGN_MANUAL: "Manual"},
}


async def async_setup_entry(
    hass: HomeAssistant, entry: HeatManagerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    manager = entry.runtime_data
    async_add_entities(RoomProfileSelect(manager, room) for room in manager.rooms.values())


class RoomProfileSelect(HeatManagerEntity, SelectEntity):
    """Choose which heating profile a room follows."""

    _attr_translation_key = "profile"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, manager, room) -> None:
        super().__init__(manager, room, "profile")

    def _labels(self) -> dict[str, str]:
        lang = (self.hass.config.language or "en").split("-")[0]
        return LABELS.get(lang, LABELS["en"])

    def _choices(self) -> dict[str, str]:
        """Map option label -> assignment value."""
        labels = self._labels()
        choices = {p["name"]: pid for pid, p in self.manager.profiles.items()}
        choices[labels[ASSIGN_FROST]] = ASSIGN_FROST
        choices[labels[ASSIGN_MANUAL]] = ASSIGN_MANUAL
        return choices

    @property
    def options(self) -> list[str]:
        return list(self._choices())

    @property
    def current_option(self) -> str | None:
        value = self.manager.assignments.get(self.room.id, ASSIGN_MANUAL)
        for label, assigned in self._choices().items():
            if assigned == value:
                return label
        return None

    async def async_select_option(self, option: str) -> None:
        value = self._choices().get(option)
        if value is None:
            raise ServiceValidationError(f"Unknown profile {option}")
        self.manager.set_assignment(self.room.id, value)
