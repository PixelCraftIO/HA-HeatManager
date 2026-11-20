"""Behaviour tests for several temperature sensors per room."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed, async_mock_service

from custom_components.heatmanager.const import DOMAIN
from custom_components.heatmanager.manager import HeatManager

CLIMATE = "climate.kids"
CLIMATE2 = "climate.kids_2"
WINDOW = "binary_sensor.kids_window"
NEAR = "sensor.kids_window_temp"
BED = "sensor.kids_bed_temp"
EXT = "number.kids_external_temperature"
WEEK_ALL_DAY = {
    day: [{"from": "06:00", "to": "22:00", "temp": 20}]
    for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
}


def climate_state(hass: HomeAssistant, entity_id: str, temp: float, current: float = 21.5) -> None:
    hass.states.async_set(
        entity_id,
        "heat",
        {"temperature": temp, "current_temperature": current, "min_temp": 4, "max_temp": 30, "target_temp_step": 0.5},
    )


def sensor(hass: HomeAssistant, entity_id: str, value: Any) -> None:
    hass.states.async_set(entity_id, str(value), {"device_class": "temperature", "unit_of_measurement": "°C"})


async def make(hass: HomeAssistant, freezer: FrozenDateTimeFactory, **room: Any):
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(dt_util.parse_datetime("2026-11-17T12:00:00+01:00"))
    climates = room.pop("climates", [CLIMATE])
    for c in climates:
        climate_state(hass, c, 18)
    hass.states.async_set(WINDOW, "off", {"device_class": "window"})
    sensor(hass, NEAR, 16)
    sensor(hass, BED, 22)
    # load the real climate component first so the mock below replaces its service
    assert await async_setup_component(hass, "climate", {})
    calls: list[ServiceCall] = async_mock_service(hass, "climate", "set_temperature")
    number_calls: list[ServiceCall] = async_mock_service(hass, "number", "set_value")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        options={
            "rooms": [
                {
                    "id": "r1",
                    "name": "Kids",
                    "climates": climates,
                    "windows": [WINDOW],
                    "area": None,
                    "temp_sensors": [NEAR, BED],
                    **room,
                }
            ],
            "frost_temp": 5.0,
            "window_delay": 30,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager: HeatManager = entry.runtime_data
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    return manager, calls, number_calls


def sent(calls: list[ServiceCall], entity_id: str = CLIMATE) -> float | None:
    values = [c.data["temperature"] for c in calls if c.data["entity_id"] in (entity_id, [entity_id])]
    return values[-1] if values else None


async def test_existing_room_without_sensors_keeps_working(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, _ = await make(hass, freezer, temp_sensors=[])
    rt = manager.runtime["r1"]
    assert rt.room_temp == 21.5 and rt.room_temp_source == "thermostats"
    assert sent(calls) == 20
    assert hass.states.get("sensor.kids_room_temperature").state == "21.5"


async def test_mean_min_max_and_weights(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    manager, _, _ = await make(hass, freezer)
    rt = manager.runtime["r1"]
    assert rt.room_temp == 19.0 and rt.room_temp_source == "sensors"
    state = hass.states.get("sensor.kids_room_temperature")
    assert state.state == "19.0"
    assert state.attributes["valid_sensors"] == [BED, NEAR]


@pytest.mark.parametrize(
    ("room", "expected"),
    [
        ({"temp_method": "min"}, 16.0),
        ({"temp_method": "max"}, 22.0),
        ({"temp_method": "primary", "primary_sensor": BED}, 22.0),
        ({"sensor_weights": {BED: 3, NEAR: 1}}, 20.5),
    ],
)
async def test_methods(hass: HomeAssistant, freezer: FrozenDateTimeFactory, room: dict, expected: float) -> None:
    manager, _, _ = await make(hass, freezer, **room)
    assert manager.runtime["r1"].room_temp == expected


async def test_failed_and_stale_sensors_fall_back(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    manager, _, _ = await make(hass, freezer, sensor_max_age=60)
    rt = manager.runtime["r1"]
    sensor(hass, NEAR, "unavailable")
    await hass.async_block_till_done()
    assert rt.room_temp == 22.0
    # BED stops reporting: after 60 min nothing valid is left, the thermostat's reading is used
    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert rt.room_temp == 21.5 and rt.room_temp_source == "thermostats"
    # an hour later a repair issue tells the user
    for _ in range(13):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "sensors_r1") is not None
    sensor(hass, BED, 20.5)
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert rt.room_temp == 20.5
    assert ir.async_get(hass).async_get_issue(DOMAIN, "sensors_r1") is None


async def test_upper_limit_stops_heating(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Daniel's example: window sensor 16 °C, bed 22 °C, target 20 °C: the mean says heat, the bed says no."""
    manager, calls, _ = await make(hass, freezer, upper_limit=1.5)
    rt = manager.runtime["r1"]
    assert rt.too_warm and rt.reason == "too_warm"
    assert sent(calls) == 17  # profile base temperature
    # still too warm inside the hysteresis
    sensor(hass, BED, 21.2)
    await hass.async_block_till_done()
    assert rt.too_warm
    sensor(hass, BED, 20.9)
    await hass.async_block_till_done()
    assert not rt.too_warm and rt.reason == "profile_block"
    assert sent(calls) == 20


async def test_upper_limit_leaves_override_alone(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, _ = await make(hass, freezer, upper_limit=1.5)
    manager.set_override("r1", 22.0)
    await hass.async_block_till_done()
    assert manager.runtime["r1"].reason == "override"
    assert sent(calls) == 22


async def test_window_near_sensor_ignored_while_open(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    manager, _, _ = await make(hass, freezer, window_near_sensors=[NEAR])
    rt = manager.runtime["r1"]
    assert rt.room_temp == 19.0
    hass.states.async_set(WINDOW, "on", {"device_class": "window"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert rt.room_temp == 22.0
    hass.states.async_set(WINDOW, "off", {"device_class": "window"})
    await hass.async_block_till_done()
    assert rt.room_temp == 22.0  # still ignored right after closing
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert rt.room_temp == 19.0


async def test_offset_compensation_per_thermostat(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, _ = await make(hass, freezer, control="offset", temp_sensors=[BED], climates=[CLIMATE, CLIMATE2])
    # room 22 °C (BED); thermostat 1 reads 21.5 → -0.5 K, thermostat 2 reads 23.5 → +1.5 K
    climate_state(hass, CLIMATE2, sent(calls, CLIMATE2) or 18, current=23.5)
    sensor(hass, BED, 22)
    rt = manager.runtime["r1"]
    # the offset is smoothed over about 30 minutes
    for _ in range(36):
        sensor(hass, BED, 22)  # the sensor keeps reporting
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert rt.offsets[CLIMATE] == pytest.approx(-0.5)
    assert sent(calls, CLIMATE) == 19.5
    assert rt.offsets[CLIMATE2] == pytest.approx(1.5, abs=0.05)
    assert sent(calls, CLIMATE2) == 21.5
    # the planned target is still 20 °C
    assert rt.target == 20


async def test_external_temperature_is_sent(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    hass.states.async_set(EXT, "20", {"min": -10, "max": 50, "step": 0.1})
    manager, calls, number_calls = await make(
        hass, freezer, control="external", external_inputs={CLIMATE: EXT}, temp_sensors=[BED]
    )
    assert number_calls and number_calls[-1].data == {"entity_id": EXT, "value": 22.0}
    assert sent(calls) == 20  # plain setpoint, the thermostat regulates with the room temperature
    count = len(number_calls)
    sensor(hass, BED, 22.05)
    await hass.async_block_till_done()
    assert len(number_calls) == count  # below 0.1 K: nothing sent
    sensor(hass, BED, 21.6)
    await hass.async_block_till_done()
    assert number_calls[-1].data["value"] == 21.6
    # refreshed at least every 15 minutes
    count = len(number_calls)
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(number_calls) > count


async def test_external_without_input_falls_back_to_offset(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, number_calls = await make(hass, freezer, control="external", temp_sensors=[BED])
    assert number_calls == []
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert manager.runtime["r1"].offsets[CLIMATE] == pytest.approx(-0.5)
    assert sent(calls) == 19.5
