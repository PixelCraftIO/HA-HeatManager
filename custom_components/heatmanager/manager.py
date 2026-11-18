"""HeatManager runtime: profiles, room assignments, windows, pause, sending."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import re
from typing import Any
import unicodedata

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_HOME,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ASSIGN_FROST,
    ASSIGN_MANUAL,
    CONF_AREA,
    CONF_AWAY_DELAY,
    CONF_AWAY_TEMP,
    CONF_CLIMATES,
    CONF_CONTROL,
    CONF_EXTERNAL,
    CONF_FROST_TEMP,
    CONF_MAX_AGE,
    CONF_OCCUPANCY,
    CONF_PRESENCE,
    CONF_PRIMARY,
    CONF_ROOM_ID,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_SENSORS,
    CONF_TEMP_METHOD,
    CONF_UPPER_LIMIT,
    CONF_VACANT_DELAY,
    CONF_VACANT_TEMP,
    CONF_WEIGHTS,
    CONF_WINDOW_DELAY,
    CONF_WINDOW_NEAR,
    CONF_WINDOWS,
    DAYS,
    DEFAULT_AWAY_DELAY,
    DEFAULT_AWAY_TEMP,
    DEFAULT_BASE_TEMP,
    DEFAULT_FROST_TEMP,
    DEFAULT_MAX_AGE,
    DEFAULT_VACANT_DELAY,
    DEFAULT_VACANT_TEMP,
    DEFAULT_WINDOW_DELAY,
    DOMAIN,
    EXTERNAL_REFRESH_MIN,
    PROBLEM_NOT_ACCEPTING,
    PROBLEM_NOT_RESPONDING,
    PROBLEM_UNAVAILABLE,
    REASON_AWAY,
    REASON_FROST,
    REASON_MANUAL,
    REASON_OVERRIDE,
    REASON_PAUSED,
    REASON_PROFILE_BASE,
    REASON_PROFILE_BLOCK,
    REASON_TOO_WARM,
    REASON_VACANT,
    REASON_VACATION,
    REASON_WINDOW,
    RECHECK_INTERVAL_MIN,
    RETRY_DELAYS,
    SIGNAL_UPDATE,
    STORAGE_KEY,
    STORAGE_VERSION,
    TEMP_MAX,
    TEMP_MIN,
    UNAVAILABLE_PROBLEM_AFTER,
    WINDOW_NEAR_GRACE_MIN,
)
from .roomtemp import (
    CONTROL_EXTERNAL,
    CONTROL_THERMOSTAT,
    CONTROLS,
    METHOD_MEAN,
    METHODS,
    OFFSET_RESEND,
    SOURCE_SENSORS,
    SOURCE_THERMOSTATS,
    combine,
    compensated,
    parse_reading,
    smooth_offset,
    too_warm,
)
from .schedule import MINUTES_PER_DAY, next_change, next_target, normalize_week, parse_time, profile_target

_LOGGER = logging.getLogger(__name__)

CLIMATE_DOMAIN = "climate"
SERVICE_SET_TEMPERATURE = "set_temperature"
NUMBER_DOMAIN = "number"
SERVICE_SET_VALUE = "set_value"
# Reasons for which a setpoint means comfort (compensated per thermostat); the others mean "stay cold"
COMFORT_REASONS = (REASON_PROFILE_BLOCK, REASON_PROFILE_BASE, REASON_AWAY, REASON_VACANT, REASON_OVERRIDE)
# Reasons the upper limit may lower (an explicit override is the user's wish and stays)
LIMITED_REASONS = (REASON_PROFILE_BLOCK, REASON_PROFILE_BASE, REASON_AWAY, REASON_VACANT)
# occupancy of a room
OCCUPIED = "occupied"
EMPTY = "empty"
UNSURE = "unsure"


def slugify_name(name: str) -> str:
    """Create a stable id from a profile name."""
    text = name.lower().replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


@dataclass
class Room:
    """A configured room."""

    id: str
    name: str
    climates: list[str]
    windows: list[str]
    area: str | None = None
    area_name: str | None = None
    # external temperature sensors and how they are combined
    sensors: list[str] = field(default_factory=list)
    method: str = METHOD_MEAN
    primary: str | None = None
    weights: dict[str, float] = field(default_factory=dict)
    window_near: list[str] = field(default_factory=list)
    max_age: int = DEFAULT_MAX_AGE  # minutes
    upper_limit: float | None = None  # K above target; None = off
    control: str = CONTROL_THERMOSTAT
    # thermostat -> number entity that takes an external temperature
    external: dict[str, str] = field(default_factory=dict)
    # motion/occupancy/presence sensors: the room is lowered while all are off for a while
    occupancy: list[str] = field(default_factory=list)
    vacant_delay: int = DEFAULT_VACANT_DELAY  # minutes
    vacant_temp: float = DEFAULT_VACANT_TEMP


@dataclass
class RoomRuntime:
    """Runtime state of a room."""

    target: float | None = None
    reason: str | None = None
    window_open: bool = False
    window_timer: CALLBACK_TYPE | None = None
    snapshot: dict[str, float] = field(default_factory=dict)
    # setpoints before a temporary override, restored afterwards when no plan applies
    override_restore: dict[str, float] = field(default_factory=dict)
    retry_timers: dict[str, CALLBACK_TYPE] = field(default_factory=dict)
    # thermostat -> what we last asked it for (after clamping)
    wanted: dict[str, float] = field(default_factory=dict)
    # thermostat -> when we first sent the current wanted setpoint
    sent_at: dict[str, datetime] = field(default_factory=dict)
    # thermostat -> problem kind (not_accepting / not_responding / unavailable)
    problems: dict[str, str] = field(default_factory=dict)
    unavailable_since: dict[str, datetime] = field(default_factory=dict)
    # room temperature
    room_temp: float | None = None
    room_temp_source: str | None = None
    readings: dict[str, float] = field(default_factory=dict)
    too_warm: bool = False
    window_closed_at: datetime | None = None
    # offset compensation: thermostat -> smoothed offset and when it was updated
    offsets: dict[str, float] = field(default_factory=dict)
    offset_at: dict[str, datetime] = field(default_factory=dict)
    # external inputs: number entity -> (value, when) last sent
    external_sent: dict[str, tuple[float, datetime]] = field(default_factory=dict)
    sensors_missing_since: datetime | None = None
    # nobody in the room for vacant_delay minutes
    vacant: bool = False
    vacant_timer: CALLBACK_TYPE | None = None


class HeatManager:
    """Owns all logic of one HeatManager config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
        self.profiles: dict[str, dict[str, Any]] = {}
        self.assignments: dict[str, str] = {}
        # room id -> assignment before the room was switched off (frost), restored when switched on
        self.previous_assignments: dict[str, str] = {}
        # room id -> {"temp": float, "until": datetime | None}
        self.overrides: dict[str, dict[str, Any]] = {}
        self.pause_active = False
        self.pause_until: datetime | None = None
        self.rooms: dict[str, Room] = {}
        self.runtime: dict[str, RoomRuntime] = {}
        self._unsubs: list[CALLBACK_TYPE] = []
        self._boundary_unsub: CALLBACK_TYPE | None = None
        self._pause_unsub: CALLBACK_TYPE | None = None
        self.vacation_until: datetime | None = None
        self._vacation_unsub: CALLBACK_TYPE | None = None
        self.away = False
        self._away_timer: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------ setup
    @property
    def frost_temp(self) -> float:
        return float(self.entry.options.get(CONF_FROST_TEMP, DEFAULT_FROST_TEMP))

    @property
    def window_delay(self) -> int:
        return int(self.entry.options.get(CONF_WINDOW_DELAY, DEFAULT_WINDOW_DELAY))

    @property
    def presence_entities(self) -> list[str]:
        return list(self.entry.options.get(CONF_PRESENCE) or [])

    @property
    def away_temp(self) -> float:
        return float(self.entry.options.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP))

    @property
    def away_delay(self) -> int:
        """Minutes everybody must be gone before lowering."""
        return int(self.entry.options.get(CONF_AWAY_DELAY, DEFAULT_AWAY_DELAY))

    async def async_load(self) -> None:
        """Load rooms from options and profiles/assignments from storage."""
        for raw in self.entry.options.get(CONF_ROOMS, []):
            room = Room(
                id=raw[CONF_ROOM_ID],
                name=raw[CONF_ROOM_NAME],
                climates=list(raw.get(CONF_CLIMATES, [])),
                windows=list(raw.get(CONF_WINDOWS, [])),
                area=raw.get(CONF_AREA),
                sensors=list(raw.get(CONF_SENSORS) or []),
                method=raw.get(CONF_TEMP_METHOD) if raw.get(CONF_TEMP_METHOD) in METHODS else METHOD_MEAN,
                primary=raw.get(CONF_PRIMARY) or None,
                weights={k: float(v) for k, v in (raw.get(CONF_WEIGHTS) or {}).items()},
                window_near=list(raw.get(CONF_WINDOW_NEAR) or []),
                max_age=int(raw.get(CONF_MAX_AGE) or DEFAULT_MAX_AGE),
                upper_limit=float(raw[CONF_UPPER_LIMIT]) if raw.get(CONF_UPPER_LIMIT) else None,
                control=raw.get(CONF_CONTROL) if raw.get(CONF_CONTROL) in CONTROLS else CONTROL_THERMOSTAT,
                external={k: v for k, v in (raw.get(CONF_EXTERNAL) or {}).items() if v},
                occupancy=list(raw.get(CONF_OCCUPANCY) or []),
                vacant_delay=int(raw.get(CONF_VACANT_DELAY) or DEFAULT_VACANT_DELAY),
                vacant_temp=float(raw.get(CONF_VACANT_TEMP) or DEFAULT_VACANT_TEMP),
            )
            if room.area and (area := ar.async_get(self.hass).async_get_area(room.area)):
                room.area_name = area.name
            self.rooms[room.id] = room
            self.runtime[room.id] = RoomRuntime()

        data = await self._store.async_load() or {}
        self.profiles = data.get("profiles", {})
        self.assignments = data.get("assignments", {})
        self.previous_assignments = {
            k: v for k, v in (data.get("previous_assignments") or {}).items() if k in self.rooms
        }
        pause = data.get("pause", {})
        self.pause_active = bool(pause.get("active"))
        until = pause.get("until")
        self.pause_until = dt_util.parse_datetime(until) if until else None
        if self.pause_active and self.pause_until and self.pause_until <= dt_util.now():
            self.pause_active, self.pause_until = False, None
        vacation = (data.get("vacation") or {}).get("until")
        self.vacation_until = dt_util.parse_datetime(vacation) if vacation else None
        if self.vacation_until and self.vacation_until <= dt_util.now():
            self.vacation_until = None
        now = dt_util.now()
        for room_id, raw in (data.get("overrides") or {}).items():
            until = dt_util.parse_datetime(raw["until"]) if raw.get("until") else None
            if room_id in self.rooms and (until is None or until > now):
                self.overrides[room_id] = {"temp": float(raw["temp"]), "until": until}
                self.runtime[room_id].override_restore = dict(raw.get("restore") or {})
        for room_id in self.rooms:
            value = self.assignments.get(room_id)
            if value not in self.profiles and value not in (ASSIGN_FROST, ASSIGN_MANUAL):
                self.assignments[room_id] = ASSIGN_MANUAL

    async def async_start(self) -> None:
        """Start listening and apply the current targets."""
        windows = [w for room in self.rooms.values() for w in room.windows]
        if windows:
            self._unsubs.append(async_track_state_change_event(self.hass, windows, self._on_window_event))
        climates = [c for room in self.rooms.values() for c in room.climates]
        if climates:
            self._unsubs.append(async_track_state_change_event(self.hass, climates, self._on_climate_event))
        sensors = sorted({s for room in self.rooms.values() for s in room.sensors})
        if sensors:
            self._unsubs.append(async_track_state_change_event(self.hass, sensors, self._on_sensor_event))
        self._unsubs.append(
            async_track_time_interval(self.hass, self._on_interval, timedelta(minutes=RECHECK_INTERVAL_MIN))
        )
        # Windows that are already open when we start
        for room in self.rooms.values():
            if self._any_window_open(room):
                self.runtime[room.id].window_open = True
        occupancy = sorted({s for room in self.rooms.values() for s in room.occupancy})
        if occupancy:
            self._unsubs.append(async_track_state_change_event(self.hass, occupancy, self._on_occupancy_event))
            for room in self.rooms.values():
                self._update_occupancy(room)
        if self.presence_entities:
            self._unsubs.append(
                async_track_state_change_event(self.hass, self.presence_entities, self._on_presence_event)
            )
            self.away = self._nobody_home()
        self._schedule_pause_end()
        self._schedule_vacation_end()
        # start clean: problems that still exist are found again
        for entity_id in climates:
            ir.async_delete_issue(self.hass, DOMAIN, f"thermostat_{entity_id}")
        for room_id in self.rooms:
            ir.async_delete_issue(self.hass, DOMAIN, f"sensors_{room_id}")
        self.evaluate(force=True)

    @callback
    def async_stop(self) -> None:
        """Stop all listeners and timers."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._boundary_unsub:
            self._boundary_unsub()
            self._boundary_unsub = None
        if self._pause_unsub:
            self._pause_unsub()
            self._pause_unsub = None
        if self._vacation_unsub:
            self._vacation_unsub()
            self._vacation_unsub = None
        if self._away_timer:
            self._away_timer()
            self._away_timer = None
        for rt in self.runtime.values():
            if rt.window_timer:
                rt.window_timer()
            if rt.vacant_timer:
                rt.vacant_timer()
                rt.vacant_timer = None
            for unsub in rt.retry_timers.values():
                unsub()
            rt.retry_timers.clear()

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(self._data_to_save, 1)

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "profiles": self.profiles,
            "assignments": self.assignments,
            "previous_assignments": self.previous_assignments,
            "overrides": {
                room_id: {
                    "temp": o["temp"],
                    "until": o["until"].isoformat() if o["until"] else None,
                    "restore": self.runtime[room_id].override_restore,
                }
                for room_id, o in self.overrides.items()
            },
            "pause": {
                "active": self.pause_active,
                "until": self.pause_until.isoformat() if self.pause_until else None,
            },
            "vacation": {"until": self.vacation_until.isoformat() if self.vacation_until else None},
        }

    # -------------------------------------------------------------- computing
    def compute(self, room: Room, now: datetime | None = None) -> tuple[float | None, str]:
        """Return (target temperature or None for 'leave alone', reason)."""
        now = now or dt_util.now()
        if self.runtime[room.id].window_open:
            return self.frost_temp, REASON_WINDOW
        if (override := self.overrides.get(room.id)) and (override["until"] is None or override["until"] > now):
            return override["temp"], REASON_OVERRIDE
        return self._limit(room, *self._plan(room, now))

    def _limit(self, room: Room, target: float | None, reason: str) -> tuple[float | None, str]:
        """Upper limit: stop heating while any sensor is too far above the target."""
        rt = self.runtime[room.id]
        if target is None or reason not in LIMITED_REASONS or room.upper_limit is None:
            rt.too_warm = False
            return target, reason
        sensors = {e: v for e, v in rt.readings.items() if e in room.sensors}
        warmest = max(sensors.values()) if sensors else None
        rt.too_warm = too_warm(warmest, target, room.upper_limit, rt.too_warm)
        if not rt.too_warm:
            return target, reason
        profile = self.profiles.get(self.assignments.get(room.id, ASSIGN_MANUAL))
        base = float(profile.get("base_temp", DEFAULT_BASE_TEMP)) if profile else None
        lowered = base if base is not None and base < target else self.frost_temp
        return min(lowered, target), REASON_TOO_WARM

    # -------------------------------------------------------- room temperature
    def _valid_reading(self, entity_id: str, now: datetime, max_age: int | None) -> float | None:
        st = self.hass.states.get(entity_id)
        if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        if max_age is not None:
            reported = getattr(st, "last_reported", None) or st.last_updated
            if now - reported > timedelta(minutes=max_age):
                return None
        return parse_reading(st.state)

    @callback
    def update_room_temperature(self, room: Room, now: datetime | None = None) -> None:
        """Recompute the room's actual temperature from its sensors (thermostats as fallback)."""
        now = now or dt_util.now()
        rt = self.runtime[room.id]
        skip_near = self._any_window_open(room) or (
            rt.window_closed_at is not None and now - rt.window_closed_at < timedelta(minutes=WINDOW_NEAR_GRACE_MIN)
        )
        readings: dict[str, float] = {}
        for entity_id in room.sensors:
            if skip_near and entity_id in room.window_near:
                continue
            if (value := self._valid_reading(entity_id, now, room.max_age)) is not None:
                readings[entity_id] = value
        value = combine(readings, room.method, room.weights, room.sensors, room.primary)
        source = SOURCE_SENSORS if value is not None else None
        if value is None:
            own = {
                c: v
                for c in room.climates
                if (st := self.hass.states.get(c)) is not None
                and (v := parse_reading(st.attributes.get("current_temperature"))) is not None
            }
            if own:
                value, source = sum(own.values()) / len(own), SOURCE_THERMOSTATS
        rt.readings = readings
        rt.room_temp = round(value, 2) if value is not None else None
        rt.room_temp_source = source

    @callback
    def _update_offsets(self, room: Room, now: datetime) -> None:
        """Track how far each thermostat's own reading is off the room temperature."""
        rt = self.runtime[room.id]
        if room.control == CONTROL_THERMOSTAT or rt.room_temp_source != SOURCE_SENSORS:
            return
        for entity_id in room.climates:
            st = self.hass.states.get(entity_id)
            own = parse_reading(st.attributes.get("current_temperature")) if st else None
            if own is None:
                continue
            last = rt.offset_at.get(entity_id)
            minutes = (now - last).total_seconds() / 60 if last else 0.0
            rt.offsets[entity_id] = smooth_offset(rt.offsets.get(entity_id), own - rt.room_temp, minutes)
            rt.offset_at[entity_id] = now

    def _external_input(self, room: Room, entity_id: str) -> str | None:
        """The usable external temperature input of a thermostat, if any."""
        if room.control != CONTROL_EXTERNAL or not (number := room.external.get(entity_id)):
            return None
        st = self.hass.states.get(number)
        if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return number

    def setpoint_for(self, room: Room, entity_id: str, target: float, reason: str | None) -> float:
        """What one thermostat should be set to so that the room reaches the target."""
        rt = self.runtime[room.id]
        if (
            room.control == CONTROL_THERMOSTAT
            or reason not in COMFORT_REASONS
            or rt.room_temp_source != SOURCE_SENSORS
            or self._external_input(room, entity_id) is not None
            or (offset := rt.offsets.get(entity_id)) is None
        ):
            return target
        st = self.hass.states.get(entity_id)
        attrs = st.attributes if st else {}
        return compensated(
            target,
            offset,
            float(attrs.get("target_temp_step") or 0.5),
            float(attrs.get("min_temp", TEMP_MIN)),
            float(attrs.get("max_temp", TEMP_MAX)),
        )

    @callback
    def _push_external(self, room: Room, now: datetime) -> None:
        """Send the room temperature to thermostats that take an external reading."""
        rt = self.runtime[room.id]
        if room.control != CONTROL_EXTERNAL or rt.room_temp_source != SOURCE_SENSORS or rt.room_temp is None:
            return
        for entity_id in room.climates:
            if (number := self._external_input(room, entity_id)) is None:
                continue
            attrs = self.hass.states.get(number).attributes
            step = float(attrs.get("step") or 0.1)
            value = round(round(rt.room_temp / step) * step, 2)
            value = max(float(attrs.get("min", value)), min(float(attrs.get("max", value)), value))
            last = rt.external_sent.get(number)
            if last and abs(last[0] - value) < 0.1 and now - last[1] < timedelta(minutes=EXTERNAL_REFRESH_MIN):
                continue
            rt.external_sent[number] = (value, now)
            self.hass.async_create_task(
                self.hass.services.async_call(
                    NUMBER_DOMAIN, SERVICE_SET_VALUE, {ATTR_ENTITY_ID: number, "value": value}, blocking=False
                ),
                eager_start=True,
            )

    @callback
    def _on_sensor_event(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        room_ids = [r.id for r in self.rooms.values() if entity_id in r.sensors]
        if room_ids:
            self.evaluate(room_ids=room_ids)

    def _plan(
        self, room: Room, now: datetime, away: bool | None = None, vacant: bool | None = None
    ) -> tuple[float | None, str]:
        """Target without window and override: vacation, pause, frost, manual or profile (lowered when away/empty)."""
        assignment = self.assignments.get(room.id, ASSIGN_MANUAL)
        controlled = assignment == ASSIGN_FROST or assignment in self.profiles
        if controlled and self.vacation_until is not None and self.vacation_until > now:
            return self.frost_temp, REASON_VACATION
        if self.pause_active and (self.pause_until is None or self.pause_until > now):
            return None, REASON_PAUSED
        if assignment == ASSIGN_FROST:
            return self.frost_temp, REASON_FROST
        profile = self.profiles.get(assignment)
        if profile is None:
            return None, REASON_MANUAL
        temp, in_block = profile_target(profile, now)
        reason = REASON_PROFILE_BLOCK if in_block else REASON_PROFILE_BASE
        if (self.away if away is None else away) and temp > self.away_temp:
            temp, reason = self.away_temp, REASON_AWAY
        if (self.runtime[room.id].vacant if vacant is None else vacant) and temp > room.vacant_temp:
            temp, reason = room.vacant_temp, REASON_VACANT
        return temp, reason

    def today(self, room: Room, now: datetime | None = None) -> list[list[Any]]:
        """Today's planned course as [from_min, to_min, temp or None, reason] (without windows and presence)."""
        now = now or dt_util.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day = DAYS[now.weekday()]
        cuts = {0, MINUTES_PER_DAY}
        profile = self.profiles.get(self.assignments.get(room.id, ASSIGN_MANUAL))
        if profile:
            for block in (profile.get("week") or {}).get(day, []):
                cuts.add(parse_time(block["from"]))
                cuts.add(parse_time(block["to"]) or MINUTES_PER_DAY)
        override = self.overrides.get(room.id)
        now_min = int((now - midnight).total_seconds() // 60)
        if override:
            cuts.add(now_min)  # an override only counts from now on
        for moment in (
            override["until"] if override else None,
            self.vacation_until,
            self.pause_until if self.pause_active else None,
        ):
            if moment is not None:
                minute = (dt_util.as_local(moment) - midnight).total_seconds() / 60
                if 0 < minute < MINUTES_PER_DAY:
                    cuts.add(int(-(-minute // 1)))  # round up to the full minute
        points = sorted(cuts)
        out: list[list[Any]] = []
        for start, end in zip(points, points[1:], strict=False):
            moment = midnight + timedelta(minutes=start)
            ov = (
                override
                if override and start >= now_min and (override["until"] is None or override["until"] > moment)
                else None
            )
            temp, reason = (ov["temp"], REASON_OVERRIDE) if ov else self._plan(room, moment, away=False, vacant=False)
            if out and out[-1][2] == temp and out[-1][3] == reason:
                out[-1][1] = end
            else:
                out.append([start, end, temp, reason])
        return out

    @callback
    def evaluate(self, force: bool = False, room_ids: list[str] | None = None) -> None:
        """Recompute targets; send to thermostats when a target changes (or force)."""
        now = dt_util.now()
        for room_id, override in list(self.overrides.items()):
            if override["until"] is not None and override["until"] <= now:
                self._end_override(room_id)
                if room_ids is not None and room_id not in room_ids:
                    room_ids = [*room_ids, room_id]
        for room in self.rooms.values():
            if room_ids is not None and room.id not in room_ids:
                continue
            rt = self.runtime[room.id]
            self.update_room_temperature(room, now)
            self._check_sensors(room, now)
            self._update_offsets(room, now)
            self._push_external(room, now)
            target, reason = self.compute(room, now)
            changed = target is not None and (rt.target is None or abs(rt.target - target) >= 0.05)
            rt.target, rt.reason = target, reason
            if target is None:
                continue
            for entity_id in room.climates:
                setpoint = self.setpoint_for(room, entity_id, target, reason)
                wanted = rt.wanted.get(entity_id)
                st = self.hass.states.get(entity_id)
                compare = self._clamp(st, setpoint) if st is not None else setpoint
                drift = wanted is not None and abs(wanted - compare) >= OFFSET_RESEND
                if changed or force or drift:
                    self._send_climate(room, entity_id, setpoint, attempt=0)
        self._schedule_next_boundary(now)
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry.entry_id}")

    @callback
    def _schedule_next_boundary(self, now: datetime) -> None:
        if self._boundary_unsub:
            self._boundary_unsub()
            self._boundary_unsub = None
        used = {self.assignments.get(r) for r in self.rooms}
        candidates = [
            when for pid in used if (profile := self.profiles.get(pid)) and (when := next_change(profile, now))
        ]
        candidates += [o["until"] for o in self.overrides.values() if o["until"] is not None and o["until"] > now]
        if candidates:
            self._boundary_unsub = async_track_point_in_time(self.hass, self._on_boundary, min(candidates))

    @callback
    def _on_boundary(self, _now: datetime) -> None:
        self._boundary_unsub = None
        self.evaluate()

    @callback
    def _on_interval(self, _now: datetime) -> None:
        self._check_unavailable()
        self.evaluate()

    # --------------------------------------------------------------- problems
    @callback
    def _check_unavailable(self) -> None:
        now = dt_util.now()
        for room in self.rooms.values():
            rt = self.runtime[room.id]
            for entity_id in room.climates:
                st = self.hass.states.get(entity_id)
                if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    since = rt.unavailable_since.setdefault(entity_id, now)
                    if (now - since).total_seconds() >= UNAVAILABLE_PROBLEM_AFTER:
                        self._set_problem(room, entity_id, PROBLEM_UNAVAILABLE)
                else:
                    rt.unavailable_since.pop(entity_id, None)
                    if rt.problems.get(entity_id) == PROBLEM_UNAVAILABLE:
                        self._clear_problem(room, entity_id)

    @callback
    def _check_sensors(self, room: Room, now: datetime) -> None:
        """Report a room whose temperature sensors all failed for an hour."""
        rt = self.runtime[room.id]
        issue_id = f"sensors_{room.id}"
        if not room.sensors or rt.room_temp_source == SOURCE_SENSORS:
            if rt.sensors_missing_since is not None:
                rt.sensors_missing_since = None
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        if rt.sensors_missing_since is None:
            rt.sensors_missing_since = now
        if (now - rt.sensors_missing_since).total_seconds() >= UNAVAILABLE_PROBLEM_AFTER:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="sensors_unavailable",
                translation_placeholders={"room": room.name, "sensors": ", ".join(room.sensors)},
            )

    @callback
    def _set_problem(self, room: Room, entity_id: str, kind: str, temp: float | None = None) -> None:
        rt = self.runtime[room.id]
        if rt.problems.get(entity_id) == kind:
            return
        rt.problems[entity_id] = kind
        st = self.hass.states.get(entity_id)
        name = (st.name if st else None) or entity_id
        if kind == PROBLEM_NOT_ACCEPTING:
            _LOGGER.warning("%s (%s) keeps ignoring the setpoint %.1f °C", name, room.name, temp or 0)
        elif kind == PROBLEM_NOT_RESPONDING:
            _LOGGER.warning(
                "%s (%s) sends no updates any more, setpoint %.1f °C not confirmed", name, room.name, temp or 0
            )
        else:
            _LOGGER.warning("%s (%s) has been unavailable for a long time", name, room.name)
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"thermostat_{entity_id}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"thermostat_{kind}",
            translation_placeholders={
                "thermostat": name,
                "entity_id": entity_id,
                "room": room.name,
                "temperature": f"{temp:.1f}" if temp is not None else "",
            },
        )
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry.entry_id}")

    @callback
    def _clear_problem(self, room: Room, entity_id: str) -> None:
        if self.runtime[room.id].problems.pop(entity_id, None) is None:
            return
        _LOGGER.info("%s works again", entity_id)
        ir.async_delete_issue(self.hass, DOMAIN, f"thermostat_{entity_id}")
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry.entry_id}")

    # ---------------------------------------------------------------- sending
    @callback
    def _send_climate(self, room: Room, entity_id: str, temp: float, attempt: int) -> None:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        temp = self._clamp(state, temp)
        current = state.attributes.get(ATTR_TEMPERATURE)
        rt = self.runtime[room.id]
        if (old := rt.retry_timers.pop(entity_id, None)) is not None:
            old()
        rt.wanted[entity_id] = temp
        if current is not None and abs(float(current) - temp) < 0.05:
            if rt.problems.get(entity_id) in (PROBLEM_NOT_ACCEPTING, PROBLEM_NOT_RESPONDING):
                self._clear_problem(room, entity_id)
            return
        _LOGGER.debug("%s: setting %s to %.1f (attempt %d)", room.name, entity_id, temp, attempt + 1)
        if attempt == 0:
            rt.sent_at[entity_id] = dt_util.utcnow()
        self.hass.async_create_task(
            self.hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: temp},
                blocking=False,
            ),
            eager_start=True,
        )
        last = attempt >= len(RETRY_DELAYS)

        @callback
        def _check(_now: datetime) -> None:
            rt.retry_timers.pop(entity_id, None)
            # Only retry while we still want this temperature
            if rt.target is None or abs(rt.wanted.get(entity_id, temp) - temp) >= 0.05:
                return
            st = self.hass.states.get(entity_id)
            if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return
            cur = st.attributes.get(ATTR_TEMPERATURE)
            if cur is None or abs(float(cur) - temp) >= 0.05:
                if last:
                    # No state report at all since the first command: the device is silent
                    # (radio/battery), even if Home Assistant still shows its last values.
                    sent = rt.sent_at.get(entity_id)
                    silent = sent is not None and st.last_reported <= sent
                    self._set_problem(
                        room, entity_id, PROBLEM_NOT_RESPONDING if silent else PROBLEM_NOT_ACCEPTING, temp
                    )
                else:
                    _LOGGER.info("%s did not take %.1f °C, sending again", entity_id, temp)
                    self._send_climate(room, entity_id, temp, attempt + 1)

        rt.retry_timers[entity_id] = async_call_later(
            self.hass, RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)], _check
        )

    @staticmethod
    def _clamp(state: Any, temp: float) -> float:
        low = state.attributes.get("min_temp", TEMP_MIN)
        high = state.attributes.get("max_temp", TEMP_MAX)
        step = state.attributes.get("target_temp_step") or 0.5
        temp = max(float(low), min(float(high), temp))
        return round(round(temp / step) * step, 1)

    # ---------------------------------------------------------------- windows
    def _any_window_open(self, room: Room) -> bool:
        return any((st := self.hass.states.get(w)) is not None and st.state == STATE_ON for w in room.windows)

    def _room_for(self, entity_id: str, attr: str) -> Room | None:
        for room in self.rooms.values():
            if entity_id in getattr(room, attr):
                return room
        return None

    @callback
    def _on_window_event(self, event: Event[EventStateChangedData]) -> None:
        room = self._room_for(event.data["entity_id"], "windows")
        if room is None:
            return
        rt = self.runtime[room.id]
        if self._any_window_open(room):
            if rt.window_open or rt.window_timer:
                return
            rt.window_timer = async_call_later(
                self.hass, self.window_delay, callback(lambda _now: self._window_opened(room))
            )
            return
        # all windows closed
        old = event.data["old_state"]
        if old is not None and old.state == STATE_ON:
            rt.window_closed_at = dt_util.now()
        if rt.window_timer:
            rt.window_timer()
            rt.window_timer = None
        if rt.window_open:
            self._window_closed(room)

    @callback
    def _window_opened(self, room: Room) -> None:
        rt = self.runtime[room.id]
        rt.window_timer = None
        if not self._any_window_open(room):
            return
        rt.snapshot = {}
        for entity_id in room.climates:
            st = self.hass.states.get(entity_id)
            if st and (temp := st.attributes.get(ATTR_TEMPERATURE)) is not None:
                rt.snapshot[entity_id] = float(temp)
        rt.window_open = True
        _LOGGER.debug("%s: window open, lowering to frost protection", room.name)
        self.evaluate(force=True, room_ids=[room.id])

    @callback
    def _window_closed(self, room: Room) -> None:
        rt = self.runtime[room.id]
        rt.window_open = False
        target, _ = self.compute(room)
        if target is None:
            # manual room or paused schedule: put back what was set before
            for entity_id, temp in rt.snapshot.items():
                self._send_climate(room, entity_id, temp, attempt=len(RETRY_DELAYS))
        rt.snapshot = {}
        rt.target = None
        self.evaluate(force=True, room_ids=[room.id])

    @callback
    def _on_climate_event(self, event: Event[EventStateChangedData]) -> None:
        old, new = event.data["old_state"], event.data["new_state"]
        if new is None or new.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        entity_id = event.data["entity_id"]
        room = self._room_for(entity_id, "climates")
        if room is not None:
            rt = self.runtime[room.id]
            if rt.room_temp_source != SOURCE_SENSORS:
                self.update_room_temperature(room)
            temp = new.attributes.get(ATTR_TEMPERATURE)
            # Thermostat confirmed our target: no retry needed any more
            wanted = rt.wanted.get(entity_id, rt.target)
            if rt.target is not None and temp is not None and wanted is not None and abs(float(temp) - wanted) < 0.05:
                if (unsub := rt.retry_timers.pop(entity_id, None)) is not None:
                    unsub()
                self._clear_problem(room, entity_id)
            if rt.problems.get(entity_id) == PROBLEM_UNAVAILABLE:
                rt.unavailable_since.pop(entity_id, None)
                self._clear_problem(room, entity_id)
        if old is None or old.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # thermostat came back: make sure it has the right target
            if room and (target := self.runtime[room.id].target) is not None:
                reason = self.runtime[room.id].reason
                self._send_climate(room, entity_id, self.setpoint_for(room, entity_id, target, reason), attempt=0)
        if new.attributes.get(ATTR_TEMPERATURE) != (old.attributes.get(ATTR_TEMPERATURE) if old else None):
            async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry.entry_id}")

    # ------------------------------------------------------------------ pause
    @callback
    def set_pause(self, active: bool, until: datetime | None = None) -> None:
        """Pause (optionally until a moment) or resume the schedule."""
        was_active = self.pause_active
        self.pause_active = active
        self.pause_until = until if active else None
        self._schedule_pause_end()
        self._save()
        if was_active and not active:
            for rt in self.runtime.values():
                rt.target = None
            self.evaluate(force=True)
        else:
            self.evaluate()

    @callback
    def _schedule_pause_end(self) -> None:
        if self._pause_unsub:
            self._pause_unsub()
            self._pause_unsub = None
        if self.pause_active and self.pause_until:
            self._pause_unsub = async_track_point_in_time(
                self.hass, callback(lambda _now: self.set_pause(False)), self.pause_until
            )

    # -------------------------------------------------------------- overrides
    @callback
    def set_override(
        self, room_id: str, temp: float, until: datetime | None = None, until_next_change: bool = False
    ) -> datetime | None:
        """Hold a room at a temperature until a moment (or the next change of its plan); return the end."""
        if room_id not in self.rooms:
            raise KeyError(room_id)
        temp = float(temp)
        if not TEMP_MIN <= temp <= TEMP_MAX:
            raise ValueError("temperature out of range")
        now = dt_util.now()
        if until_next_change:
            until = self.next_plan_change(room_id, now)
            if until is None:
                raise ValueError("room has no upcoming change")
        if until is not None and until <= now:
            raise ValueError("end must be in the future")
        room, rt = self.rooms[room_id], self.runtime[room_id]
        if room_id not in self.overrides:
            rt.override_restore = {}
            for entity_id in room.climates:
                st = self.hass.states.get(entity_id)
                if st and (cur := st.attributes.get(ATTR_TEMPERATURE)) is not None:
                    rt.override_restore[entity_id] = float(cur)
        self.overrides[room_id] = {"temp": round(temp, 1), "until": until}
        self._save()
        self.evaluate(force=True, room_ids=[room_id])
        return until

    @callback
    def clear_override(self, room_id: str) -> None:
        """End a room's override now and go back to its plan."""
        if room_id not in self.rooms:
            raise KeyError(room_id)
        if room_id in self.overrides:
            self._end_override(room_id)
            self.evaluate(force=True, room_ids=[room_id])

    @callback
    def _end_override(self, room_id: str) -> None:
        self.overrides.pop(room_id, None)
        room, rt = self.rooms[room_id], self.runtime[room_id]
        target, _ = self.compute(room)
        if target is None:
            # manual room or paused schedule: put back what was set before
            for entity_id, temp in rt.override_restore.items():
                self._send_climate(room, entity_id, temp, attempt=len(RETRY_DELAYS))
        rt.override_restore = {}
        rt.target = None
        self._save()

    def next_plan_change(self, room_id: str, now: datetime | None = None) -> datetime | None:
        """When the room's own plan next changes its target (None for manual/frost rooms)."""
        profile = self.profiles.get(self.assignments.get(room_id, ASSIGN_MANUAL))
        if profile is None:
            return None
        when, _ = next_target(profile, now or dt_util.now())
        return when

    # ------------------------------------------------------- vacation, presence
    @callback
    def set_vacation(self, until: datetime | None) -> None:
        """Frost protection for all controlled rooms until a moment (None ends it)."""
        if until is not None and until <= dt_util.now():
            raise ValueError("end must be in the future")
        ended = self.vacation_until is not None and until is None
        self.vacation_until = until
        self._schedule_vacation_end()
        self._save()
        if ended:
            for rt in self.runtime.values():
                rt.target = None
            self.evaluate(force=True)
        else:
            self.evaluate()

    @callback
    def _schedule_vacation_end(self) -> None:
        if self._vacation_unsub:
            self._vacation_unsub()
            self._vacation_unsub = None
        if self.vacation_until:
            self._vacation_unsub = async_track_point_in_time(
                self.hass, callback(lambda _now: self.set_vacation(None)), self.vacation_until
            )

    def _nobody_home(self) -> bool:
        """True when every presence entity is known and away."""
        if not self.presence_entities:
            return False
        for entity_id in self.presence_entities:
            st = self.hass.states.get(entity_id)
            if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return False  # unsure: rather keep it warm
            if st.state in (STATE_HOME, STATE_ON):
                return False
        return True

    @callback
    def _on_presence_event(self, _event: Event[EventStateChangedData]) -> None:
        if not self._nobody_home():
            if self._away_timer:
                self._away_timer()
                self._away_timer = None
            if self.away:
                _LOGGER.debug("Somebody is home again")
                self.away = False
                self.evaluate()
            return
        if self.away or self._away_timer:
            return

        @callback
        def _gone(_now: datetime) -> None:
            self._away_timer = None
            if self._nobody_home():
                _LOGGER.debug("Nobody home, lowering to %.1f °C", self.away_temp)
                self.away = True
                self.evaluate()

        self._away_timer = async_call_later(self.hass, self.away_delay * 60, _gone)

    # -------------------------------------------------------------- occupancy
    def _occupancy(self, room: Room) -> str:
        """Occupied when any sensor is on; unsure while one has no usable state (then keep it warm)."""
        unsure = False
        for entity_id in room.occupancy:
            st = self.hass.states.get(entity_id)
            if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                unsure = True
            elif st.state == STATE_ON:
                return OCCUPIED
        return UNSURE if unsure else EMPTY

    @callback
    def _update_occupancy(self, room: Room) -> bool:
        """Follow the room's occupancy sensors; return True when the room became empty or occupied."""
        rt = self.runtime[room.id]
        if not room.occupancy:
            return False
        if self._occupancy(room) != EMPTY:
            if rt.vacant_timer:
                rt.vacant_timer()
                rt.vacant_timer = None
            if rt.vacant:
                _LOGGER.debug("%s: occupied again", room.name)
                rt.vacant = False
                return True
            return False
        if rt.vacant or rt.vacant_timer:
            return False
        # all off: count from the last time any of them changed (also covers a restart)
        last = max(st.last_changed for e in room.occupancy if (st := self.hass.states.get(e)) is not None)
        remaining = room.vacant_delay * 60 - (dt_util.utcnow() - last).total_seconds()
        if remaining <= 0:
            _LOGGER.debug("%s: nobody there, lowering to at most %.1f °C", room.name, room.vacant_temp)
            rt.vacant = True
            return True

        @callback
        def _empty(_now: datetime) -> None:
            rt.vacant_timer = None
            if self._occupancy(room) == EMPTY and not rt.vacant:
                _LOGGER.debug("%s: nobody there, lowering to at most %.1f °C", room.name, room.vacant_temp)
                rt.vacant = True
                self.evaluate(room_ids=[room.id])

        rt.vacant_timer = async_call_later(self.hass, remaining, _empty)
        return False

    @callback
    def _on_occupancy_event(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        changed = [r.id for r in self.rooms.values() if entity_id in r.occupancy and self._update_occupancy(r)]
        if changed:
            self.evaluate(room_ids=changed)

    # --------------------------------------------------------------- profiles
    @callback
    def save_profile(self, data: dict[str, Any], profile_id: str | None = None) -> str:
        """Create or update a profile; return its id."""
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("name required")
        if slugify_name(name) in SPECIAL_SLUGS:
            raise ValueError("name reserved")
        week = normalize_week(data.get("week"))
        base = float(data.get("base_temp", DEFAULT_BASE_TEMP))
        if not TEMP_MIN <= base <= TEMP_MAX:
            raise ValueError("base temperature out of range")
        for pid, other in self.profiles.items():
            if pid != profile_id and other["name"].casefold() == name.casefold():
                raise ValueError("name already used")
        if profile_id is None:
            base_id = slugify_name(name) or "profile"
            profile_id, n = base_id, 2
            while profile_id in self.profiles or profile_id in (ASSIGN_FROST, ASSIGN_MANUAL):
                profile_id, n = f"{base_id}_{n}", n + 1
        elif profile_id not in self.profiles:
            raise KeyError(profile_id)
        color = data.get("color") or None
        if color is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(color)):
            raise ValueError("invalid color")
        self.profiles[profile_id] = {
            "name": name,
            "icon": data.get("icon") or "mdi:radiator",
            "color": color,
            "base_temp": round(base, 1),
            "week": week,
        }
        self._save()
        self.evaluate(room_ids=[r for r, p in self.assignments.items() if p == profile_id])
        return profile_id

    @callback
    def delete_profile(self, profile_id: str) -> None:
        """Delete a profile; rooms using it become manual."""
        if profile_id not in self.profiles:
            raise KeyError(profile_id)
        del self.profiles[profile_id]
        for room_id, value in list(self.assignments.items()):
            if value == profile_id:
                self.assignments[room_id] = ASSIGN_MANUAL
        self._save()
        self.evaluate()

    @callback
    def set_assignment(self, room_id: str, value: str) -> None:
        """Assign a profile (or frost/manual) to a room."""
        if room_id not in self.rooms:
            raise KeyError(room_id)
        if value not in self.profiles and value not in (ASSIGN_FROST, ASSIGN_MANUAL):
            raise ValueError(f"unknown profile {value}")
        self.assignments[room_id] = value
        if room_id in self.overrides:
            self.overrides.pop(room_id)
            self.runtime[room_id].override_restore = {}
        self._save()
        self.runtime[room_id].target = None
        self.evaluate(force=True, room_ids=[room_id])

    @callback
    def set_room_on(self, room_id: str, on: bool) -> None:
        """Switch a room off (frost protection) or back on (the assignment it had before)."""
        if room_id not in self.rooms:
            raise KeyError(room_id)
        current = self.assignments.get(room_id, ASSIGN_MANUAL)
        if not on:
            if current != ASSIGN_FROST:
                self.previous_assignments[room_id] = current
                self.set_assignment(room_id, ASSIGN_FROST)
            return
        if current == ASSIGN_FROST:
            previous = self.previous_assignments.pop(room_id, ASSIGN_MANUAL)
            if previous not in self.profiles and previous != ASSIGN_MANUAL:
                previous = ASSIGN_MANUAL
            self.set_assignment(room_id, previous)

    @callback
    def set_room_temperature(self, room_id: str, temp: float) -> datetime | None:
        """A temperature set on the room itself (its climate entity, voice assistants).

        Rooms with a plan hold it until the plan's next change, manual rooms pass it straight
        to their thermostats, rooms on frost protection hold it until the override is ended.
        """
        if room_id not in self.rooms:
            raise KeyError(room_id)
        temp = float(temp)
        if not TEMP_MIN <= temp <= TEMP_MAX:
            raise ValueError("temperature out of range")
        room = self.rooms[room_id]
        if self.assignments.get(room_id, ASSIGN_MANUAL) == ASSIGN_MANUAL and room_id not in self.overrides:
            for entity_id in room.climates:
                self._send_climate(room, entity_id, temp, attempt=len(RETRY_DELAYS))
            return None
        if self.next_plan_change(room_id) is not None:
            return self.set_override(room_id, temp, until_next_change=True)
        return self.set_override(room_id, temp)

    # ------------------------------------------------------------------ views
    def room_info(self, room: Room) -> dict[str, Any]:
        """Describe a room for entities and the card."""
        rt = self.runtime[room.id]
        assignment = self.assignments.get(room.id, ASSIGN_MANUAL)
        info: dict[str, Any] = {
            "id": room.id,
            "name": room.name,
            "climates": room.climates,
            "windows": room.windows,
            "profile": assignment,
            "target": rt.target,
            "reason": rt.reason,
            "window_open": rt.window_open,
            "next_change": None,
            "next_temp": None,
            "override": None,
            "plan_change": None,
            "problems": [{"entity_id": e, "kind": k} for e, k in rt.problems.items()],
            "room_temp": rt.room_temp,
            "room_temp_source": rt.room_temp_source,
            "sensors": room.sensors,
            "sensors_valid": sorted(rt.readings),
            "too_warm": rt.too_warm,
            "control": room.control,
            "occupancy": bool(room.occupancy),
            "vacant": rt.vacant,
            "vacant_temp": room.vacant_temp if room.occupancy else None,
        }
        now = dt_util.now()
        info["today"] = self.today(room, now)
        profile = self.profiles.get(assignment)
        if (override := self.overrides.get(room.id)) is not None:
            info["override"] = {
                "temp": override["temp"],
                "until": override["until"].isoformat() if override["until"] else None,
            }
        if profile and rt.reason in (REASON_PROFILE_BLOCK, REASON_PROFILE_BASE):
            when, temp = next_target(profile, now)
            info["next_change"] = when.isoformat() if when else None
            info["next_temp"] = temp
        if profile and (when := self.next_plan_change(room.id, now)):
            info["plan_change"] = when.isoformat()
        return info

    def as_dict(self) -> dict[str, Any]:
        """Full state for the frontend."""
        return {
            "profiles": [{"id": pid, **p} for pid, p in self.profiles.items()],
            "rooms": [self.room_info(r) for r in self.rooms.values()],
            "pause": {
                "active": self.pause_active,
                "until": self.pause_until.isoformat() if self.pause_until else None,
            },
            "vacation": {"until": self.vacation_until.isoformat() if self.vacation_until else None},
            "presence": {
                "configured": bool(self.presence_entities),
                "away": self.away,
                "away_temp": self.away_temp,
            },
            "settings": {"frost_temp": self.frost_temp, "window_delay": self.window_delay},
        }


SPECIAL_SLUGS = {"frost", "manual", "frostschutz", "manuell"}


def get_manager(hass: HomeAssistant) -> HeatManager:
    """Return the (single) loaded manager."""
    managers: dict[str, HeatManager] = hass.data.get(DOMAIN, {})
    if not managers:
        raise LookupError("HeatManager is not set up")
    return next(iter(managers.values()))
