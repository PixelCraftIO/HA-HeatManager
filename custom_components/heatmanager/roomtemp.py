"""Pure room temperature logic (no Home Assistant imports, easy to test).

A room can have several temperature sensors. They are combined into one
actual room temperature; the thermostats' own readings are only a fallback.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

METHOD_MEAN = "mean"
METHOD_MIN = "min"
METHOD_MAX = "max"
METHOD_PRIMARY = "primary"
METHODS = (METHOD_MEAN, METHOD_MIN, METHOD_MAX, METHOD_PRIMARY)

CONTROL_THERMOSTAT = "thermostat"
CONTROL_EXTERNAL = "external"
CONTROL_OFFSET = "offset"
CONTROLS = (CONTROL_THERMOSTAT, CONTROL_EXTERNAL, CONTROL_OFFSET)

SOURCE_SENSORS = "sensors"
SOURCE_THERMOSTATS = "thermostats"

# Plausible readings; anything else is treated as a broken sensor
VALID_MIN = -10.0
VALID_MAX = 50.0

# Offset compensation (control mode "offset")
OFFSET_LIMIT = 3.0
OFFSET_TIME_CONSTANT_MIN = 30.0
OFFSET_RESEND = 0.5

# Upper limit: heat again once the warmest sensor is this far below the limit
UPPER_LIMIT_HYSTERESIS = 0.5


def parse_reading(value: object) -> float | None:
    """Return a plausible temperature from a state value, else None."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or not VALID_MIN <= number <= VALID_MAX:
        return None
    return number


def combine(
    readings: Mapping[str, float],
    method: str = METHOD_MEAN,
    weights: Mapping[str, float] | None = None,
    order: Sequence[str] = (),
    primary: str | None = None,
) -> float | None:
    """Combine valid readings (entity -> °C) into one room temperature.

    Sensors with weight 0 do not count (they still serve display and the upper
    limit). ``order`` is the configured sensor order, used by the primary
    method to pick the next sensor when the primary one is not valid.
    """
    weights = weights or {}
    counted = {e: v for e, v in readings.items() if weights.get(e, 1.0) > 0}
    if not counted:
        return None
    if method == METHOD_MIN:
        return min(counted.values())
    if method == METHOD_MAX:
        return max(counted.values())
    if method == METHOD_PRIMARY:
        for entity_id in [primary, *order]:
            if entity_id and entity_id in counted:
                return counted[entity_id]
        return next(iter(counted.values()))
    total = sum(weights.get(e, 1.0) for e in counted)
    return sum(v * weights.get(e, 1.0) for e, v in counted.items()) / total


def too_warm(warmest: float | None, target: float, limit: float | None, was_too_warm: bool) -> bool:
    """Upper limit with hysteresis: is any sensor too far above the target?"""
    if warmest is None or limit is None or limit <= 0:
        return False
    if was_too_warm:
        return warmest > target + limit - UPPER_LIMIT_HYSTERESIS
    return warmest > target + limit


def smooth_offset(previous: float | None, measured: float, minutes: float) -> float:
    """Exponentially smooth a thermostat's offset (its reading minus the room's)."""
    measured = max(-OFFSET_LIMIT, min(OFFSET_LIMIT, measured))
    if previous is None:
        return measured
    alpha = 1 - math.exp(-max(minutes, 0.0) / OFFSET_TIME_CONSTANT_MIN)
    return previous + (measured - previous) * alpha


def compensated(target: float, offset: float, step: float = 0.5, low: float = 4.0, high: float = 30.0) -> float:
    """Setpoint for a thermostat whose own sensor reads ``offset`` K off the room."""
    value = target + max(-OFFSET_LIMIT, min(OFFSET_LIMIT, offset))
    step = step if step and step > 0 else 0.5
    value = round(round(value / step) * step, 1)
    return max(low, min(high, value))
