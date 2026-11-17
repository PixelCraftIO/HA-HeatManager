"""WebSocket API used by the HeatManager card."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import SIGNAL_UPDATE
from .manager import HeatManager, get_manager


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register all commands."""
    for handler in (
        ws_subscribe,
        ws_save_profile,
        ws_delete_profile,
        ws_set_room_profile,
        ws_room_override,
        ws_room_clear_override,
        ws_pause,
        ws_resume,
    ):
        websocket_api.async_register_command(hass, handler)


def _manager_or_error(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg_id: int
) -> HeatManager | None:
    try:
        return get_manager(hass)
    except LookupError:
        connection.send_error(msg_id, "not_loaded", "HeatManager is not set up")
        return None


@websocket_api.websocket_command({vol.Required("type"): "heatmanager/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Send the full state now and after every change."""
    manager = _manager_or_error(hass, connection, msg["id"])
    if manager is None:
        return

    @callback
    def _push() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], manager.as_dict()))

    unsub = async_dispatcher_connect(hass, f"{SIGNAL_UPDATE}_{manager.entry.entry_id}", _push)
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"])
    _push()


_BLOCK = vol.Schema({vol.Required("from"): str, vol.Required("to"): str, vol.Required("temp"): vol.Coerce(float)})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "heatmanager/profile/save",
        vol.Optional("profile_id"): str,
        vol.Required("name"): str,
        vol.Optional("icon"): str,
        vol.Optional("base_temp"): vol.Coerce(float),
        vol.Optional("week"): {str: [_BLOCK]},
    }
)
@callback
def ws_save_profile(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Create or update a profile."""
    manager = _manager_or_error(hass, connection, msg["id"])
    if manager is None:
        return
    data = {k: msg[k] for k in ("name", "icon", "base_temp", "week") if k in msg}
    existing = manager.profiles.get(msg.get("profile_id", ""))
    if existing:
        data = {**existing, **data}
    try:
        profile_id = manager.save_profile(data, msg.get("profile_id"))
    except KeyError:
        connection.send_error(msg["id"], "not_found", "Unknown profile")
        return
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], {"profile_id": profile_id})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "heatmanager/profile/delete", vol.Required("profile_id"): str})
@callback
def ws_delete_profile(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Delete a profile."""
    manager = _manager_or_error(hass, connection, msg["id"])
    if manager is None:
        return
    try:
        manager.delete_profile(msg["profile_id"])
    except KeyError:
        connection.send_error(msg["id"], "not_found", "Unknown profile")
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "heatmanager/room/set_profile", vol.Required("room_id"): str, vol.Required("profile"): str}
)
@callback
def ws_set_room_profile(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Assign a profile to a room."""
    manager = _manager_or_error(hass, connection, msg["id"])
    if manager is None:
        return
    try:
        manager.set_assignment(msg["room_id"], msg["profile"])
    except (KeyError, ValueError) as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "heatmanager/room/override",
        vol.Required("room_id"): str,
        vol.Required("temp"): vol.Coerce(float),
        vol.Exclusive("hours", "end"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=24 * 14)),
        vol.Exclusive("until_next_change", "end"): bool,
    }
)
@callback
def ws_room_override(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Hold a room at a temperature for some hours, until its next plan change, or until cleared."""
    manager = _manager_or_error(hass, connection, msg["id"])
    if manager is None:
        return
    until = dt_util.now() + timedelta(hours=msg["hours"]) if "hours" in msg else None
    try:
        manager.set_override(msg["room_id"], msg["temp"], until, until_next_change=msg.get("until_next_change", False))
    except (KeyError, ValueError) as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "heatmanager/room/clear_override", vol.Required("room_id"): str}
)
@callback
def ws_room_clear_override(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """End a room's override."""
    manager = _manager_or_error(hass, connection, msg["id"])
    if manager is None:
        return
    try:
        manager.clear_override(msg["room_id"])
    except KeyError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "heatmanager/pause",
        vol.Exclusive("hours", "end"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=24 * 60)),
        vol.Exclusive("until", "end"): str,
    }
)
@callback
def ws_pause(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Pause the schedule for some hours, until a moment, or indefinitely."""
    manager = _manager_or_error(hass, connection, msg["id"])
    if manager is None:
        return
    until = None
    if "hours" in msg:
        until = dt_util.now() + timedelta(hours=msg["hours"])
    elif "until" in msg:
        parsed = dt_util.parse_datetime(msg["until"])
        if parsed is None:
            connection.send_error(msg["id"], "invalid_format", "Invalid date")
            return
        until = dt_util.as_local(parsed if parsed.tzinfo else parsed.replace(tzinfo=dt_util.get_default_time_zone()))
        if until <= dt_util.now():
            connection.send_error(msg["id"], "invalid_format", "Date must be in the future")
            return
    manager.set_pause(True, until)
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "heatmanager/resume"})
@callback
def ws_resume(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Resume the schedule."""
    manager = _manager_or_error(hass, connection, msg["id"])
    if manager is None:
        return
    manager.set_pause(False)
    connection.send_result(msg["id"])
