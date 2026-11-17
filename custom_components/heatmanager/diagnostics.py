"""Diagnostics for bug reports (Settings › Devices & services › HeatManager › ⋮ › Download diagnostics)."""

from __future__ import annotations

from typing import Any

from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

from . import HeatManagerConfigEntry
from .const import CONF_PRESENCE, VERSION

CLIMATE_ATTRS = (
    ATTR_TEMPERATURE,
    "current_temperature",
    "min_temp",
    "max_temp",
    "target_temp_step",
    "hvac_mode",
    "hvac_modes",
    "preset_mode",
)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: HeatManagerConfigEntry) -> dict[str, Any]:
    """Return everything needed to understand why a room has its target."""
    manager = entry.runtime_data
    options = dict(entry.options)
    # who lives here is nobody else's business: only say how many presence entities there are
    options[CONF_PRESENCE] = f"{len(options.get(CONF_PRESENCE) or [])} entities"

    def _state(entity_id: str) -> dict[str, Any] | None:
        st = hass.states.get(entity_id)
        if st is None:
            return None
        return {
            "state": st.state,
            "attributes": {k: st.attributes[k] for k in CLIMATE_ATTRS if k in st.attributes},
            "last_changed": st.last_changed.isoformat(),
            "last_updated": st.last_updated.isoformat(),
        }

    rooms = []
    for room in manager.rooms.values():
        rt = manager.runtime[room.id]
        info = manager.room_info(room)
        rooms.append(
            {
                **info,
                "wanted": rt.wanted,
                "retry_pending": sorted(rt.retry_timers),
                "window_snapshot": rt.snapshot,
                "override_restore": rt.override_restore,
                "climate_states": {c: _state(c) for c in room.climates},
                "window_states": {w: (st.state if (st := hass.states.get(w)) else None) for w in room.windows},
            }
        )

    return {
        "version": VERSION,
        "options": options,
        "profiles": manager.profiles,
        "assignments": manager.assignments,
        "pause": {
            "active": manager.pause_active,
            "until": manager.pause_until.isoformat() if manager.pause_until else None,
        },
        "vacation_until": manager.vacation_until.isoformat() if manager.vacation_until else None,
        "away": manager.away,
        "rooms": rooms,
    }
