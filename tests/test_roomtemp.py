"""Tests for the pure room temperature logic."""

from __future__ import annotations

import pytest

from custom_components.heatmanager.roomtemp import (
    METHOD_MAX,
    METHOD_MEAN,
    METHOD_MIN,
    METHOD_PRIMARY,
    combine,
    compensated,
    parse_reading,
    smooth_offset,
    too_warm,
)

WINDOW, BED = "sensor.window", "sensor.bed"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("21.4", 21.4), (19, 19.0), ("unavailable", None), (None, None), ("nan", None), ("85", None), ("-40", None)],
)
def test_parse_reading(value, expected) -> None:
    assert parse_reading(value) == expected


def test_combine_methods() -> None:
    readings = {WINDOW: 16.0, BED: 22.0}
    assert combine(readings, METHOD_MEAN) == 19.0
    assert combine(readings, METHOD_MIN) == 16.0
    assert combine(readings, METHOD_MAX) == 22.0
    assert combine(readings, METHOD_PRIMARY, order=[WINDOW, BED], primary=BED) == 22.0
    assert combine({}, METHOD_MEAN) is None


def test_weighted_mean_and_zero_weight() -> None:
    readings = {WINDOW: 16.0, BED: 22.0}
    assert combine(readings, METHOD_MEAN, {BED: 3, WINDOW: 1}) == 20.5
    # weight 0: only shown and used for the upper limit, not counted
    assert combine(readings, METHOD_MEAN, {WINDOW: 0}) == 22.0
    assert combine({WINDOW: 16.0}, METHOD_MEAN, {WINDOW: 0}) is None


def test_primary_falls_back_in_order() -> None:
    assert combine({WINDOW: 16.0}, METHOD_PRIMARY, order=[BED, WINDOW], primary=BED) == 16.0


def test_upper_limit_with_hysteresis() -> None:
    assert not too_warm(22.0, 20.0, None, False)
    assert not too_warm(21.5, 20.0, 1.5, False)
    assert too_warm(21.6, 20.0, 1.5, False)
    # stays too warm until 0.5 K below the limit
    assert too_warm(21.2, 20.0, 1.5, True)
    assert not too_warm(21.0, 20.0, 1.5, True)


def test_offset_smoothing_and_limits() -> None:
    assert smooth_offset(None, 1.5, 0) == 1.5
    assert smooth_offset(None, 6.0, 0) == 3.0
    half = smooth_offset(0.0, 2.0, 30)
    assert 1.2 < half < 1.3  # one time constant: about 63 %
    assert smooth_offset(1.0, 2.0, 0) == 1.0


def test_compensated_setpoint() -> None:
    # thermostat reads 1.5 K too warm: ask it for 1.5 K more
    assert compensated(20.0, 1.5) == 21.5
    assert compensated(20.0, 1.3) == 21.5  # rounded to the device step
    assert compensated(20.0, -5.0) == 17.0  # limited to ±3 K
    assert compensated(29.0, 2.0, high=30.0) == 30.0
