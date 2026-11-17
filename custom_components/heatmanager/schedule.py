"""Pure weekly-schedule logic (no Home Assistant imports, easy to test)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
import re
from typing import Any

from .const import DAYS, TEMP_MAX, TEMP_MIN

MINUTES_PER_DAY = 1440
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def parse_time(value: str) -> int:
    """Parse 'HH:MM' (or 'HH:MM:SS', '24:00') into minutes after midnight."""
    match = _TIME_RE.match(str(value).strip())
    if not match:
        raise ValueError(f"Invalid time: {value!r}")
    hours, minutes = int(match.group(1)), int(match.group(2))
    total = hours * 60 + minutes
    if minutes > 59 or total > MINUTES_PER_DAY:
        raise ValueError(f"Invalid time: {value!r}")
    return total


def format_time(minutes: int) -> str:
    """Format minutes after midnight as 'HH:MM' ('24:00' for end of day)."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass(frozen=True)
class Block:
    """A time block of one day with its temperature."""

    start: int
    end: int
    temp: float


def normalize_week(week: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    """Validate a week definition and return it in canonical form.

    Input per day: list of {"from": "HH:MM", "to": "HH:MM", "temp": number}.
    "to" of "00:00" or "24:00" means end of day. Blocks must not overlap.
    """
    week = week or {}
    unknown = set(week) - set(DAYS)
    if unknown:
        raise ValueError(f"Unknown day(s): {', '.join(sorted(unknown))}")
    result: dict[str, list[dict[str, Any]]] = {}
    for day in DAYS:
        blocks: list[Block] = []
        for raw in week.get(day) or []:
            start = parse_time(raw["from"])
            end = parse_time(raw["to"])
            if end == 0:
                end = MINUTES_PER_DAY
            if start >= MINUTES_PER_DAY or end <= start:
                raise ValueError(f"{day}: block {raw['from']}-{raw['to']} is empty or reversed")
            temp = float(raw["temp"])
            if not TEMP_MIN <= temp <= TEMP_MAX:
                raise ValueError(f"{day}: temperature {temp} out of range")
            blocks.append(Block(start, end, round(temp, 1)))
        blocks.sort(key=lambda b: b.start)
        for prev, nxt in zip(blocks, blocks[1:], strict=False):
            if nxt.start < prev.end:
                raise ValueError(f"{day}: blocks {format_time(prev.start)} and {format_time(nxt.start)} overlap")
        result[day] = [{"from": format_time(b.start), "to": format_time(b.end), "temp": b.temp} for b in blocks]
    return result


def _blocks(week: dict[str, list[dict[str, Any]]], day: str) -> list[Block]:
    return [
        Block(parse_time(b["from"]), parse_time(b["to"]) or MINUTES_PER_DAY, float(b["temp"]))
        for b in week.get(day, [])
    ]


def _midnight(moment: datetime) -> datetime:
    return datetime.combine(moment.date(), time(0), tzinfo=moment.tzinfo)


def active_block(week: dict[str, list[dict[str, Any]]], moment: datetime) -> Block | None:
    """Return the block active at the given moment, if any."""
    minute = moment.hour * 60 + moment.minute
    for block in _blocks(week, DAYS[moment.weekday()]):
        if block.start <= minute < block.end:
            return block
    return None


def profile_target(profile: dict[str, Any], moment: datetime) -> tuple[float, bool]:
    """Return (temperature, inside_block) for a profile at a moment."""
    block = active_block(profile.get("week", {}), moment)
    if block is not None:
        return block.temp, True
    return float(profile.get("base_temp", 17.0)), False


def next_change(profile: dict[str, Any], moment: datetime) -> datetime | None:
    """Return the next moment the profile's target may change (block start or end)."""
    week = profile.get("week", {})
    midnight = _midnight(moment)
    for offset in range(8):
        day_start = midnight + timedelta(days=offset)
        day = DAYS[day_start.weekday()]
        boundaries = sorted({m for b in _blocks(week, day) for m in (b.start, b.end)})
        for minute in boundaries:
            candidate = day_start + timedelta(minutes=minute)
            if candidate > moment:
                return candidate
    return None


def next_target(profile: dict[str, Any], moment: datetime) -> tuple[datetime | None, float | None]:
    """Return (when, temperature) of the next real target change of a profile."""
    current, _ = profile_target(profile, moment)
    probe = moment
    for _ in range(64):
        when = next_change(profile, probe)
        if when is None:
            return None, None
        temp, _ = profile_target(profile, when)
        if abs(temp - current) >= 0.05:
            return when, temp
        probe = when
    return None, None
