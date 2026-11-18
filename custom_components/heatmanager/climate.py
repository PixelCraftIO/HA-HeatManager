"""Each room as a thermostat of its own: for the thermostat tile, voice assistants, HomeKit, Google …"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import HeatManagerConfigEntry
from .const import ASSIGN_FROST, ASSIGN_MANUAL, TEMP_MAX, TEMP_MIN
from .entity import HeatManagerEntity
from .select import LABELS


async def async_setup_entry(
    hass: HomeAssistant, entry: HeatManagerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    manager = entry.runtime_data
    async_add_entities(RoomClimate(manager, room) for room in manager.rooms.values())


class RoomClimate(HeatManagerEntity, ClimateEntity):
    """The room as one thermostat.

    Heat = the room follows HeatManager (profile or manual), Off = frost protection.
    Presets are the heating profiles. A temperature set here overrides the room until its
    plan changes next (manual rooms: passed straight to their thermostats).
    """

    _attr_name = None  # the room's name
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = TEMP_MIN
    _attr_max_temp = TEMP_MAX
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, manager, room) -> None:
        super().__init__(manager, room, "climate")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # setpoints and heating state come from the room's thermostats
        self.async_on_remove(async_track_state_change_event(self.hass, self.room.climates, self._on_thermostat))

    @callback
    def _on_thermostat(self, _event: Event[EventStateChangedData]) -> None:
        self.async_write_ha_state()

    # ------------------------------------------------------------------ state
    def _labels(self) -> dict[str, str]:
        lang = (self.hass.config.language or "en").split("-")[0]
        return LABELS.get(lang, LABELS["en"])

    def _presets(self) -> dict[str, str]:
        """Map preset label -> assignment value."""
        labels = self._labels()
        presets = {p["name"]: pid for pid, p in self.manager.profiles.items()}
        presets[labels[ASSIGN_FROST]] = ASSIGN_FROST
        presets[labels[ASSIGN_MANUAL]] = ASSIGN_MANUAL
        return presets

    def _thermostats(self) -> list[Any]:
        return [
            st
            for entity_id in self.room.climates
            if (st := self.hass.states.get(entity_id)) is not None
            and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ]

    @property
    def available(self) -> bool:
        return bool(self._thermostats())

    @property
    def _assignment(self) -> str:
        return self.manager.assignments.get(self.room.id, ASSIGN_MANUAL)

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.OFF if self._assignment == ASSIGN_FROST else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        actions = [st.attributes.get("hvac_action") for st in self._thermostats()]
        actions = [a for a in actions if a]
        if HVACAction.HEATING in actions:
            return HVACAction.HEATING
        if not actions:
            return None
        return HVACAction.OFF if self.hvac_mode == HVACMode.OFF else HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        return self.manager.runtime[self.room.id].room_temp

    @property
    def target_temperature(self) -> float | None:
        target = self.manager.runtime[self.room.id].target
        if target is not None:
            return target
        # manual or paused: what the thermostats are set to
        values = [float(t) for st in self._thermostats() if (t := st.attributes.get(ATTR_TEMPERATURE)) is not None]
        return round(sum(values) / len(values), 1) if values else None

    @property
    def preset_modes(self) -> list[str]:
        return list(self._presets())

    @property
    def preset_mode(self) -> str | None:
        for label, value in self._presets().items():
            if value == self._assignment:
                return label
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rt = self.manager.runtime[self.room.id]
        override = self.manager.overrides.get(self.room.id)
        return {
            "reason": rt.reason,
            "override_until": override["until"].isoformat() if override and override["until"] else None,
            "vacant": rt.vacant if self.room.occupancy else None,
        }

    # ---------------------------------------------------------------- actions
    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (mode := kwargs.get("hvac_mode")) is not None:
            await self.async_set_hvac_mode(mode)
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        try:
            self.manager.set_room_temperature(self.room.id, float(temp))
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self.manager.set_room_on(self.room.id, hvac_mode != HVACMode.OFF)

    async def async_turn_on(self) -> None:
        self.manager.set_room_on(self.room.id, True)

    async def async_turn_off(self) -> None:
        self.manager.set_room_on(self.room.id, False)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        value = self._presets().get(preset_mode)
        if value is None:
            raise ServiceValidationError(f"Unknown profile {preset_mode}")
        self.manager.set_assignment(self.room.id, value)
