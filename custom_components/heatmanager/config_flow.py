"""Config and options flow for HeatManager."""

from __future__ import annotations

from typing import Any
import uuid

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_AREA,
    CONF_AWAY_DELAY,
    CONF_AWAY_TEMP,
    CONF_CLIMATES,
    CONF_FROST_TEMP,
    CONF_PRESENCE,
    CONF_ROOM_ID,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_WINDOW_DELAY,
    CONF_WINDOWS,
    DEFAULT_AWAY_DELAY,
    DEFAULT_AWAY_TEMP,
    DEFAULT_FROST_TEMP,
    DEFAULT_WINDOW_DELAY,
    DOMAIN,
    NAME,
)

CONF_ROOM = "room"


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
    }
    area_key = vol.Optional(CONF_AREA, description={"suggested_value": room.get(CONF_AREA)})
    schema[area_key] = selector.AreaSelector()
    return vol.Schema(schema)


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
                return self._save(**{CONF_ROOMS: [*self._rooms, room]})
        return self.async_show_form(step_id="add_room", data_schema=_room_schema(user_input), errors=errors)

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
                rooms = [room if r[CONF_ROOM_ID] == room[CONF_ROOM_ID] else r for r in self._rooms]
                return self._save(**{CONF_ROOMS: rooms})
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
            CONF_AREA: user_input.get(CONF_AREA) or None,
        }
