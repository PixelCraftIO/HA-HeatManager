"""Config and options flow for HeatManager."""

from __future__ import annotations

from typing import Any
import uuid

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector
import voluptuous as vol

from .const import (
    CONF_AREA,
    CONF_AWAY_DELAY,
    CONF_AWAY_TEMP,
    CONF_CLIMATES,
    CONF_CONTROL,
    CONF_EXTERNAL,
    CONF_FROST_TEMP,
    CONF_MAX_AGE,
    CONF_PRESENCE,
    CONF_PRIMARY,
    CONF_ROOM_ID,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_SENSORS,
    CONF_TEMP_METHOD,
    CONF_UPPER_LIMIT,
    CONF_WEIGHTS,
    CONF_WINDOW_DELAY,
    CONF_WINDOW_NEAR,
    CONF_WINDOWS,
    DEFAULT_AWAY_DELAY,
    DEFAULT_AWAY_TEMP,
    DEFAULT_FROST_TEMP,
    DEFAULT_MAX_AGE,
    DEFAULT_WINDOW_DELAY,
    DOMAIN,
    NAME,
)
from .roomtemp import CONTROL_EXTERNAL, CONTROL_THERMOSTAT, CONTROLS, METHOD_MEAN, METHODS

CONF_ROOM = "room"
# weight fields are numbered (weight_1 …) so they get proper labels
MAX_WEIGHTED = 10


def _settings_schema(frost: float, delay: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_FROST_TEMP, default=frost): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=4, max=12, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_WINDOW_DELAY, default=delay): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=900, step=5, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )


def _room_schema(room: dict[str, Any] | None = None) -> vol.Schema:
    room = room or {}
    schema: dict[Any, Any] = {
        vol.Required(CONF_ROOM_NAME, default=room.get(CONF_ROOM_NAME, vol.UNDEFINED)): selector.TextSelector(),
        vol.Required(CONF_CLIMATES, default=room.get(CONF_CLIMATES, vol.UNDEFINED)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="climate", multiple=True)
        ),
        vol.Optional(CONF_WINDOWS, default=room.get(CONF_WINDOWS, [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
        ),
        vol.Optional(CONF_SENSORS, default=room.get(CONF_SENSORS, [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="temperature", multiple=True)
        ),
    }
    area_key = vol.Optional(CONF_AREA, description={"suggested_value": room.get(CONF_AREA)})
    schema[area_key] = selector.AreaSelector()
    return vol.Schema(schema)


def _box(low: float, high: float, step: float, unit: str) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=low, max=high, step=step, unit_of_measurement=unit, mode=selector.NumberSelectorMode.BOX
        )
    )


def _temperature_schema(hass: Any, room: dict[str, Any]) -> vol.Schema:
    """How the room temperature is formed and how the thermostats use it."""
    sensors: list[str] = room.get(CONF_SENSORS) or []

    def _label(entity_id: str) -> str:
        st = hass.states.get(entity_id)
        return f"{st.name} ({entity_id})" if st else entity_id

    sensor_options = [selector.SelectOptionDict(value=e, label=_label(e)) for e in sensors]
    schema: dict[Any, Any] = {
        vol.Required(CONF_TEMP_METHOD, default=room.get(CONF_TEMP_METHOD) or METHOD_MEAN): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(METHODS), translation_key="temp_method", mode=selector.SelectSelectorMode.DROPDOWN
            )
        ),
    }
    if sensor_options:
        primary = room.get(CONF_PRIMARY) if room.get(CONF_PRIMARY) in sensors else None
        schema[vol.Optional(CONF_PRIMARY, description={"suggested_value": primary})] = selector.SelectSelector(
            selector.SelectSelectorConfig(options=sensor_options, mode=selector.SelectSelectorMode.DROPDOWN)
        )
        near = [e for e in room.get(CONF_WINDOW_NEAR) or [] if e in sensors]
        schema[vol.Optional(CONF_WINDOW_NEAR, default=near)] = selector.SelectSelector(
            selector.SelectSelectorConfig(options=sensor_options, multiple=True)
        )
    schema[vol.Required(CONF_MAX_AGE, default=room.get(CONF_MAX_AGE) or DEFAULT_MAX_AGE)] = _box(5, 1440, 5, "min")
    schema[vol.Required(CONF_UPPER_LIMIT, default=room.get(CONF_UPPER_LIMIT) or 0)] = _box(0, 5, 0.5, "K")
    schema[vol.Required(CONF_CONTROL, default=room.get(CONF_CONTROL) or CONTROL_THERMOSTAT)] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(CONTROLS), translation_key="control", mode=selector.SelectSelectorMode.LIST
        )
    )
    if len(sensors) > 1:
        weights = room.get(CONF_WEIGHTS) or {}
        for i, entity_id in enumerate(sensors[:MAX_WEIGHTED], 1):
            schema[vol.Required(f"weight_{i}", default=float(weights.get(entity_id, 1)))] = _box(0, 10, 0.5, "×")
    return vol.Schema(schema)


def _weights_legend(hass: Any, room: dict[str, Any]) -> str:
    """Which sensor the numbered weight fields belong to."""
    sensors: list[str] = room.get(CONF_SENSORS) or []
    if len(sensors) < 2:
        return ""
    names = []
    for i, entity_id in enumerate(sensors[:MAX_WEIGHTED], 1):
        st = hass.states.get(entity_id)
        names.append(f"{i} = {st.name if st else entity_id}")
    return "\n\n" + " · ".join(names)


def _suggest_external(hass: Any, climate: str) -> str | None:
    """Find a number entity on the thermostat's device that takes an external temperature."""
    registry = er.async_get(hass)
    entry = registry.async_get(climate)
    if entry is None or entry.device_id is None:
        return None
    for candidate in er.async_entries_for_device(registry, entry.device_id):
        if candidate.domain != "number":
            continue
        text = " ".join(
            str(x).lower() for x in (candidate.entity_id, candidate.original_name, candidate.translation_key) if x
        )
        if "external" in text and "temp" in text:
            return candidate.entity_id
    return None


class HeatManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup: global settings. Rooms are added in the options."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={},
                options={
                    CONF_ROOMS: [],
                    CONF_FROST_TEMP: float(user_input[CONF_FROST_TEMP]),
                    CONF_WINDOW_DELAY: int(user_input[CONF_WINDOW_DELAY]),
                },
            )
        return self.async_show_form(
            step_id="user", data_schema=_settings_schema(DEFAULT_FROST_TEMP, DEFAULT_WINDOW_DELAY)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HeatManagerOptionsFlow()


class HeatManagerOptionsFlow(OptionsFlow):
    """Manage rooms and settings."""

    def __init__(self) -> None:
        self._room_id: str | None = None
        # room being added or edited, saved after its last step
        self._pending: dict[str, Any] = {}

    @property
    def _rooms(self) -> list[dict[str, Any]]:
        return list(self.config_entry.options.get(CONF_ROOMS, []))

    def _save(self, **changes: Any) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, **changes})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = ["add_room"]
        if self._rooms:
            options += ["edit_room", "remove_room"]
        options += ["presence", "settings"]
        return self.async_show_menu(step_id="init", menu_options=options)

    async def async_step_add_room(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            room = self._clean_room(user_input, uuid.uuid4().hex[:8])
            if not room[CONF_CLIMATES]:
                errors[CONF_CLIMATES] = "no_climate"
            elif any(r[CONF_ROOM_NAME].casefold() == room[CONF_ROOM_NAME].casefold() for r in self._rooms):
                errors[CONF_ROOM_NAME] = "name_exists"
            else:
                self._pending = room
                return await self.async_step_room_temperature()
        return self.async_show_form(step_id="add_room", data_schema=_room_schema(user_input), errors=errors)

    async def async_step_room_temperature(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        room = self._pending
        if user_input is not None:
            sensors = room.get(CONF_SENSORS) or []
            room[CONF_TEMP_METHOD] = user_input.get(CONF_TEMP_METHOD) or METHOD_MEAN
            room[CONF_PRIMARY] = user_input.get(CONF_PRIMARY) if user_input.get(CONF_PRIMARY) in sensors else None
            room[CONF_WINDOW_NEAR] = [e for e in user_input.get(CONF_WINDOW_NEAR) or [] if e in sensors]
            room[CONF_MAX_AGE] = int(user_input.get(CONF_MAX_AGE) or DEFAULT_MAX_AGE)
            room[CONF_UPPER_LIMIT] = float(user_input.get(CONF_UPPER_LIMIT) or 0) or None
            room[CONF_CONTROL] = user_input.get(CONF_CONTROL) or CONTROL_THERMOSTAT
            room[CONF_WEIGHTS] = {
                e: float(user_input[f"weight_{i}"])
                for i, e in enumerate(sensors[:MAX_WEIGHTED], 1)
                if len(sensors) > 1 and f"weight_{i}" in user_input
            }
            if room[CONF_CONTROL] == CONTROL_EXTERNAL:
                return await self.async_step_room_external()
            room[CONF_EXTERNAL] = {}
            return self._store_room(room)
        return self.async_show_form(
            step_id="room_temperature",
            data_schema=_temperature_schema(self.hass, room),
            description_placeholders={"room": room[CONF_ROOM_NAME], "weights": _weights_legend(self.hass, room)},
        )

    async def async_step_room_external(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        room = self._pending
        climates = room[CONF_CLIMATES]
        numbered = list(enumerate(climates[:MAX_WEIGHTED], 1))
        if user_input is not None:
            room[CONF_EXTERNAL] = {c: user_input[f"input_{i}"] for i, c in numbered if user_input.get(f"input_{i}")}
            return self._store_room(room)
        current = room.get(CONF_EXTERNAL) or {}
        schema = {
            vol.Optional(
                f"input_{i}", description={"suggested_value": current.get(c) or _suggest_external(self.hass, c)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="number"))
            for i, c in numbered
        }
        legend = " · ".join(f"{i} = {st.name if (st := self.hass.states.get(c)) else c}" for i, c in numbered)
        return self.async_show_form(
            step_id="room_external",
            data_schema=vol.Schema(schema),
            description_placeholders={"room": room[CONF_ROOM_NAME], "thermostats": legend},
        )

    def _store_room(self, room: dict[str, Any]) -> ConfigFlowResult:
        rooms = self._rooms
        if any(r[CONF_ROOM_ID] == room[CONF_ROOM_ID] for r in rooms):
            rooms = [room if r[CONF_ROOM_ID] == room[CONF_ROOM_ID] else r for r in rooms]
        else:
            rooms.append(room)
        return self._save(**{CONF_ROOMS: rooms})

    def _room_choices(self) -> selector.SelectSelector:
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[selector.SelectOptionDict(value=r[CONF_ROOM_ID], label=r[CONF_ROOM_NAME]) for r in self._rooms]
            )
        )

    async def async_step_edit_room(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._room_id = user_input[CONF_ROOM]
            return await self.async_step_edit_room_details()
        return self.async_show_form(
            step_id="edit_room", data_schema=vol.Schema({vol.Required(CONF_ROOM): self._room_choices()})
        )

    async def async_step_edit_room_details(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = next(r for r in self._rooms if r[CONF_ROOM_ID] == self._room_id)
        errors: dict[str, str] = {}
        if user_input is not None:
            room = self._clean_room(user_input, current[CONF_ROOM_ID])
            if not room[CONF_CLIMATES]:
                errors[CONF_CLIMATES] = "no_climate"
            elif any(
                r[CONF_ROOM_ID] != room[CONF_ROOM_ID]
                and r[CONF_ROOM_NAME].casefold() == room[CONF_ROOM_NAME].casefold()
                for r in self._rooms
            ):
                errors[CONF_ROOM_NAME] = "name_exists"
            else:
                # keep the temperature settings for the next step
                self._pending = {**current, **room}
                return await self.async_step_room_temperature()
        return self.async_show_form(
            step_id="edit_room_details",
            data_schema=_room_schema(user_input or current),
            errors=errors,
            description_placeholders={"room": current[CONF_ROOM_NAME]},
        )

    async def async_step_remove_room(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            remove = set(user_input[CONF_ROOMS])
            return self._save(**{CONF_ROOMS: [r for r in self._rooms if r[CONF_ROOM_ID] not in remove]})
        choices = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=r[CONF_ROOM_ID], label=r[CONF_ROOM_NAME]) for r in self._rooms
                ],
                multiple=True,
            )
        )
        return self.async_show_form(step_id="remove_room", data_schema=vol.Schema({vol.Required(CONF_ROOMS): choices}))

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = self.config_entry.options
        if user_input is not None:
            return self._save(
                **{
                    CONF_FROST_TEMP: float(user_input[CONF_FROST_TEMP]),
                    CONF_WINDOW_DELAY: int(user_input[CONF_WINDOW_DELAY]),
                }
            )
        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(
                options.get(CONF_FROST_TEMP, DEFAULT_FROST_TEMP), options.get(CONF_WINDOW_DELAY, DEFAULT_WINDOW_DELAY)
            ),
        )

    async def async_step_presence(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = self.config_entry.options
        if user_input is not None:
            return self._save(
                **{
                    CONF_PRESENCE: list(user_input.get(CONF_PRESENCE) or []),
                    CONF_AWAY_TEMP: float(user_input[CONF_AWAY_TEMP]),
                    CONF_AWAY_DELAY: int(user_input[CONF_AWAY_DELAY]),
                }
            )
        schema = vol.Schema(
            {
                vol.Optional(CONF_PRESENCE, default=options.get(CONF_PRESENCE, [])): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["person", "device_tracker", "group", "binary_sensor", "input_boolean"], multiple=True
                    )
                ),
                vol.Required(CONF_AWAY_TEMP, default=options.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP)): (
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5, max=22, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX
                        )
                    )
                ),
                vol.Required(CONF_AWAY_DELAY, default=options.get(CONF_AWAY_DELAY, DEFAULT_AWAY_DELAY)): (
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=240, step=1, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX
                        )
                    )
                ),
            }
        )
        return self.async_show_form(step_id="presence", data_schema=schema)

    @staticmethod
    def _clean_room(user_input: dict[str, Any], room_id: str) -> dict[str, Any]:
        return {
            CONF_ROOM_ID: room_id,
            CONF_ROOM_NAME: str(user_input[CONF_ROOM_NAME]).strip(),
            CONF_CLIMATES: list(user_input.get(CONF_CLIMATES) or []),
            CONF_WINDOWS: list(user_input.get(CONF_WINDOWS) or []),
            CONF_SENSORS: list(user_input.get(CONF_SENSORS) or []),
            CONF_AREA: user_input.get(CONF_AREA) or None,
        }
